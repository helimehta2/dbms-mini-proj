from flask import Flask, render_template, request, redirect, url_for
import pymysql
import os

app = Flask(__name__)
app.secret_key = "dbms-railway-reservation-key"

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "heli",
    "password": "",
    "database": "railway_db",
    "port": 3306,
    "autocommit": False
}

def get_db():
    conn = pymysql.connect(**MYSQL_CONFIG)
    return conn

@app.route("/")
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT train_id, train_name, source, destination, total_seats, available_seats, fare FROM trains")
    trains = cursor.fetchall()
    conn.close()
    return render_template("index.html", trains=trains)

# =====================================================================
# EDGE CASE 1 & 3: Concurrency Control ('FOR UPDATE') & ACID Atomicity
# Row-level lock prevents simultaneous double-booking in MySQL.
# =====================================================================
@app.route("/book", methods=["POST"])
def book():
    train_id = int(request.form["train_id"])
    passenger_name = request.form.get("passenger_name", "").strip()
    try:
        age = int(request.form["age"])
    except (ValueError, TypeError):
        return "Invalid age provided!", 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.begin()

        # 1. Row-level write lock for concurrency
        cursor.execute("SELECT available_seats, total_seats FROM trains WHERE train_id = %s FOR UPDATE", (train_id,))
        seat_data = cursor.fetchone()
        if not seat_data or seat_data[0] <= 0:
            conn.rollback()
            conn.close()
            return "Booking Rejected: No available seats on this train! (Overbooking prevented)", 400

        # 2. Insert booking (MySQL Trigger trg_decrement_seat_on_booking automatically updates train available_seats)
        cursor.execute("INSERT INTO bookings (user_id, train_id) VALUES (1, %s)", (train_id,))
        booking_id = cursor.lastrowid

        # 3. Insert passenger record
        cursor.execute("INSERT INTO passengers (booking_id, passenger_name, age) VALUES (%s, %s, %s)", 
                       (booking_id, passenger_name, age))

        # Commit all atomically
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Transaction Aborted (All changes safely rolled back): {e}", 500
    finally:
        conn.close()

    return redirect(url_for("bookings"))

@app.route("/bookings")
def bookings():
    conn = get_db()
    cursor = conn.cursor()
    
    # Query directly from MySQL VIEW: v_booking_manifest (Relational 3-table INNER JOIN)
    query = """
    SELECT booking_id, train_name, passenger_name, age, status, booking_date, source, destination, fare
    FROM v_booking_manifest
    ORDER BY booking_id DESC
    """
    cursor.execute(query)
    all_bookings = cursor.fetchall()
    conn.close()
    return render_template("bookings.html", bookings=all_bookings)

# =====================================================================
# EDGE CASE 2: Idempotent Cancellation (Double-Cancellation Guard)
# =====================================================================
@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel(booking_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.begin()

        # Check if booking is in CONFIRMED state before cancelling
        cursor.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = %s AND status = 'CONFIRMED'", (booking_id,))
        
        if cursor.rowcount == 0:
            conn.rollback()
            conn.close()
            return "Cancellation rejected: This ticket is already cancelled or does not exist.", 400

        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Cancellation failed: {e}", 500
    finally:
        conn.close()

    return redirect(url_for("bookings"))

@app.route("/analytics")
def analytics():
    conn = get_db()
    cursor = conn.cursor()

    # Query from MySQL VIEW: v_train_occupancy_report (Uses LEFT OUTER JOIN & GROUP BY & Aggregate functions)
    query = """
    SELECT train_id, train_name, source, destination, total_seats, available_seats, 
           booked_seats, occupancy_pct, confirmed_bookings, total_revenue
    FROM v_train_occupancy_report
    ORDER BY occupancy_pct DESC, train_id ASC
    """
    cursor.execute(query)
    reports = cursor.fetchall()

    # High-level aggregate statistics across all trains
    summary_query = """
    SELECT 
        COUNT(DISTINCT t.train_id) AS total_trains,
        COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN 1 ELSE 0 END), 0) AS total_confirmed_passengers,
        COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN t.fare ELSE 0 END), 0) AS total_revenue
    FROM trains t
    LEFT JOIN bookings b ON t.train_id = b.train_id
    """
    cursor.execute(summary_query)
    totals = cursor.fetchone()
    conn.close()

    return render_template("analytics.html", reports=reports, totals=totals)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
