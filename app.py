from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "railway.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db()
    with open("schema.sql", "r") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()

@app.route("/")
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT train_id, train_name, source, destination, total_seats, available_seats, fare FROM trains")
    trains = cursor.fetchall()
    conn.close()
    return render_template("index.html", trains=trains)

@app.route("/book", methods=["POST"])
def book():
    train_id = int(request.form["train_id"])
    passenger_name = request.form["passenger_name"]
    age = int(request.form["age"])

    conn = get_db()
    cursor = conn.cursor()

    try:
        # 1. Pre-check available seats
        cursor.execute("SELECT available_seats FROM trains WHERE train_id = ?", (train_id,))
        seat_data = cursor.fetchone()
        if not seat_data or seat_data[0] <= 0:
            conn.close()
            return "No available seats on this train!", 400

        # 2. Insert booking record (TRIGGER: trg_decrement_seat_on_booking will automatically decrement available_seats)
        cursor.execute("INSERT INTO bookings (user_id, train_id) VALUES (1, ?)", (train_id,))
        booking_id = cursor.lastrowid

        # 3. Insert passenger record linked by foreign key
        cursor.execute("INSERT INTO passengers (booking_id, passenger_name, age) VALUES (?, ?, ?)", (booking_id, passenger_name, age))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Booking Transaction failed: {e}", 500
    finally:
        conn.close()

    return redirect(url_for("bookings"))

@app.route("/bookings")
def bookings():
    conn = get_db()
    cursor = conn.cursor()
    
    # Query directly from SQL VIEW: v_booking_manifest (Relational 3-table INNER JOIN)
    query = """
    SELECT booking_id, train_name, passenger_name, age, status, booking_date, source, destination, fare
    FROM v_booking_manifest
    ORDER BY booking_id DESC
    """
    cursor.execute(query)
    all_bookings = cursor.fetchall()
    conn.close()
    return render_template("bookings.html", bookings=all_bookings)

@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel(booking_id):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # UPDATE status to CANCELLED (TRIGGER: trg_increment_seat_on_cancellation will automatically increment available_seats)
        cursor.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = ? AND status = 'CONFIRMED'", (booking_id,))
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

    # Query from SQL VIEW: v_train_occupancy_report (Uses LEFT OUTER JOIN & GROUP BY & Aggregate functions)
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

# Initialize database schema, views, triggers, and seed data on startup
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
