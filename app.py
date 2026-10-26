from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)
DB_NAME = "railway.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS trains (
    train_id INTEGER PRIMARY KEY,
    train_name TEXT NOT NULL,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    total_seats INTEGER NOT NULL,
    available_seats INTEGER NOT NULL,
    fare REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    train_id INTEGER NOT NULL,
    booking_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'CONFIRMED',
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (train_id) REFERENCES trains(train_id)
);

CREATE TABLE IF NOT EXISTS passengers (
    passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    passenger_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
);

-- Seed Indian Railways Trains
INSERT OR REPLACE INTO trains (train_id, train_name, source, destination, total_seats, available_seats, fare)
VALUES 
(201, 'Vande Bharat Express', 'New Delhi (NDLS)', 'Varanasi Junction (BSB)', 50, 50, 1750.00),
(202, 'Mumbai Rajdhani Express', 'Mumbai Central (MMCT)', 'Delhi Hazrat Nizamuddin (NZM)', 30, 30, 2400.00),
(203, 'Chennai Shatabdi Express', 'Bengaluru City (SBC)', 'Chennai Central (MAS)', 40, 40, 950.00),
(204, 'Tejas Express', 'Mumbai CSMT (CSMT)', 'Goa Madgaon (MAO)', 35, 35, 1580.00),
(205, 'Howrah Duronto Express', 'Kolkata Howrah (HWH)', 'New Delhi (NDLS)', 45, 45, 2200.00);

INSERT OR IGNORE INTO users (user_id, name, email)
VALUES (1, 'Default Student', 'student@example.com');
"""

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Force drop trains table to instantly purge any old US routes (101, 102, 103)
    cursor.execute("DROP TABLE IF EXISTS trains")
    cursor.executescript(SCHEMA)
    conn.commit()
    conn.close()

@app.route("/")
def index():
    conn = sqlite3.connect(DB_NAME)
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

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        cursor.execute("UPDATE trains SET available_seats = available_seats - 1 WHERE train_id = ? AND available_seats > 0", (train_id,))
        if cursor.rowcount == 0:
            conn.close()
            return "No available seats!", 400

        cursor.execute("INSERT INTO bookings (user_id, train_id) VALUES (1, ?)", (train_id,))
        booking_id = cursor.lastrowid
        cursor.execute("INSERT INTO passengers (booking_id, passenger_name, age) VALUES (?, ?, ?)", (booking_id, passenger_name, age))
        conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Transaction failed: {e}", 500
    finally:
        conn.close()

    return redirect(url_for("bookings"))

@app.route("/bookings")
def bookings():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    query = """
    SELECT b.booking_id, t.train_name, p.passenger_name, p.age, b.status, b.booking_date
    FROM bookings b
    JOIN trains t ON b.train_id = t.train_id
    JOIN passengers p ON b.booking_id = p.booking_id
    ORDER BY b.booking_id DESC
    """
    cursor.execute(query)
    all_bookings = cursor.fetchall()
    conn.close()
    return render_template("bookings.html", bookings=all_bookings)

@app.route("/cancel/<int:booking_id>", methods=["POST"])
def cancel(booking_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    try:
        cursor.execute("SELECT train_id, status FROM bookings WHERE booking_id = ?", (booking_id,))
        row = cursor.fetchone()
        
        if row and row[1] == 'CONFIRMED':
            train_id = row[0]
            cursor.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = ?", (booking_id,))
            cursor.execute("UPDATE trains SET available_seats = available_seats + 1 WHERE train_id = ?", (train_id,))
            conn.commit()
    except Exception as e:
        conn.rollback()
        return f"Cancellation failed: {e}", 500
    finally:
        conn.close()

    return redirect(url_for("bookings"))

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=5000)