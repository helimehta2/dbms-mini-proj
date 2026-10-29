PRAGMA foreign_keys = ON;

-- =======================================================
-- 1. TABLES DEFINITIONS (RELATIONAL SCHEMA WITH CHECK CONSTRAINTS)
-- =======================================================

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
    total_seats INTEGER NOT NULL CHECK (total_seats > 0),
    available_seats INTEGER NOT NULL CHECK (available_seats >= 0 AND available_seats <= total_seats),
    fare REAL NOT NULL CHECK (fare > 0)
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    train_id INTEGER NOT NULL,
    booking_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'CONFIRMED' CHECK (status IN ('CONFIRMED', 'CANCELLED')),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (train_id) REFERENCES trains(train_id)
);

CREATE TABLE IF NOT EXISTS passengers (
    passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    passenger_name TEXT NOT NULL CHECK (length(trim(passenger_name)) > 0),
    age INTEGER NOT NULL CHECK (age > 0 AND age <= 120),
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
);

-- =======================================================
-- 2. INDEXES (QUERY OPTIMIZATION)
-- =======================================================
CREATE INDEX IF NOT EXISTS idx_trains_route ON trains(source, destination);
CREATE INDEX IF NOT EXISTS idx_bookings_train ON bookings(train_id);
CREATE INDEX IF NOT EXISTS idx_passengers_booking ON passengers(booking_id);

-- =======================================================
-- 3. SQL VIEWS (MULTI-TABLE JOINS & ABSTRACTION)
-- =======================================================

-- VIEW 1: Relational 3-Table Inner Join (Bookings + Trains + Passengers)
DROP VIEW IF EXISTS v_booking_manifest;
CREATE VIEW v_booking_manifest AS
SELECT 
    b.booking_id,
    t.train_id,
    t.train_name,
    t.source,
    t.destination,
    t.fare,
    p.passenger_name,
    p.age,
    b.status,
    b.booking_date
FROM bookings b
JOIN trains t ON b.train_id = t.train_id
JOIN passengers p ON b.booking_id = p.booking_id;

-- VIEW 2: Analytical View with LEFT OUTER JOIN, GROUP BY, and Aggregates
DROP VIEW IF EXISTS v_train_occupancy_report;
CREATE VIEW v_train_occupancy_report AS
SELECT 
    t.train_id,
    t.train_name,
    t.source,
    t.destination,
    t.total_seats,
    t.available_seats,
    (t.total_seats - t.available_seats) AS booked_seats,
    ROUND(((t.total_seats - t.available_seats) * 100.0 / t.total_seats), 1) AS occupancy_pct,
    COUNT(CASE WHEN b.status = 'CONFIRMED' THEN 1 END) AS confirmed_bookings,
    COALESCE(SUM(CASE WHEN b.status = 'CONFIRMED' THEN t.fare ELSE 0 END), 0) AS total_revenue
FROM trains t
LEFT JOIN bookings b ON t.train_id = b.train_id
GROUP BY t.train_id;

-- =======================================================
-- 4. DATABASE TRIGGERS (EDGE CASE HANDLING & BUSINESS LOGIC)
-- =======================================================

-- TRIGGER 1 [Edge Case 1: Overbooking & Race Condition Guard]:
-- Aborts insert at the engine level if available_seats <= 0
DROP TRIGGER IF EXISTS trg_check_seat_availability;
CREATE TRIGGER trg_check_seat_availability
BEFORE INSERT ON bookings
WHEN (SELECT available_seats FROM trains WHERE train_id = NEW.train_id) <= 0
BEGIN
    SELECT RAISE(ABORT, 'DBMS Race Condition Guard: Overbooking prevented! No seats available.');
END;

-- TRIGGER 2 [Edge Case 1 & 3: Atomic Inventory Decrement]:
-- Decrements available_seats immediately after confirmed booking within the same transaction
DROP TRIGGER IF EXISTS trg_decrement_seat_on_booking;
CREATE TRIGGER trg_decrement_seat_on_booking
AFTER INSERT ON bookings
WHEN NEW.status = 'CONFIRMED'
BEGIN
    UPDATE trains 
    SET available_seats = available_seats - 1 
    WHERE train_id = NEW.train_id AND available_seats > 0;
END;

-- TRIGGER 3 [Edge Case 2: Double-Cancellation & Inventory Inflation Guard]:
-- Only increments seat if transitioning from CONFIRMED -> CANCELLED, and caps at total_seats
DROP TRIGGER IF EXISTS trg_increment_seat_on_cancellation;
CREATE TRIGGER trg_increment_seat_on_cancellation
AFTER UPDATE OF status ON bookings
WHEN OLD.status = 'CONFIRMED' AND NEW.status = 'CANCELLED'
BEGIN
    UPDATE trains 
    SET available_seats = MIN(available_seats + 1, total_seats) 
    WHERE train_id = NEW.train_id;
END;

-- =======================================================
-- 5. INITIAL MASTER DATA (TRAINS & USER)
-- =======================================================
INSERT OR IGNORE INTO trains (train_id, train_name, source, destination, total_seats, available_seats, fare)
VALUES 
(201, 'Vande Bharat Express', 'New Delhi (NDLS)', 'Varanasi Junction (BSB)', 50, 50, 1750.00),
(202, 'Mumbai Rajdhani Express', 'Mumbai Central (MMCT)', 'Delhi Nizamuddin (NZM)', 30, 30, 2400.00),
(203, 'Chennai Shatabdi Express', 'Bengaluru City (SBC)', 'Chennai Central (MAS)', 40, 40, 950.00),
(204, 'Tejas Express', 'Mumbai CSMT (CSMT)', 'Goa Madgaon (MAO)', 35, 35, 1580.00),
(205, 'Howrah Duronto Express', 'Kolkata Howrah (HWH)', 'New Delhi (NDLS)', 45, 45, 2200.00);

INSERT OR IGNORE INTO users (user_id, name, email)
VALUES (1, 'Heli Mehta', 'helimehta230@gmail.com');

-- =======================================================
-- 6. RECORDED RESERVATION DATA (HELI & NEEVA'S BOOKINGS)
-- =======================================================

-- Reservation 1: Ticket booked by Heli on Tejas Express
INSERT OR IGNORE INTO bookings (booking_id, user_id, train_id, booking_date, status)
VALUES (1, 1, 204, '2026-10-29 04:24:50', 'CONFIRMED');

INSERT OR IGNORE INTO passengers (passenger_id, booking_id, passenger_name, age)
VALUES (1, 1, 'heli', 21);

-- Reservation 2: Ticket booked on Vande Bharat Express
INSERT OR IGNORE INTO bookings (booking_id, user_id, train_id, booking_date, status)
VALUES (101, 1, 201, '2026-10-29 04:34:11', 'CONFIRMED');

INSERT OR IGNORE INTO passengers (passenger_id, booking_id, passenger_name, age)
VALUES (501, 101, 'Heli Mehta', 21);

-- Reservation 3: Ticket booked by Neeva on Mumbai Rajdhani Express
INSERT OR IGNORE INTO bookings (booking_id, user_id, train_id, booking_date, status)
VALUES (102, 1, 202, '2026-10-29 05:04:02', 'CONFIRMED');

INSERT OR IGNORE INTO passengers (passenger_id, booking_id, passenger_name, age)
VALUES (502, 102, 'neeva mehta', 27);


-- =======================================================
-- 7. DEMONSTRATION SQL QUERIES & RESULT SETS
-- =======================================================

-- Query 1: View all records from the PASSENGERS table
SELECT passenger_id, booking_id, passenger_name, age 
FROM passengers;

/*
RESULT SET FOR QUERY 1:
+--------------+------------+----------------+-----+
| passenger_id | booking_id | passenger_name | age |
+--------------+------------+----------------+-----+
| 1            | 1          | heli           | 21  |
| 501          | 101        | Heli Mehta     | 21  |
| 502          | 102        | neeva mehta    | 27  |
+--------------+------------+----------------+-----+
*/

-- Query 2: Retrieve reservation specifically for 'neeva mehta'
SELECT 
    b.booking_id,
    t.train_name,
    t.source || ' -> ' || t.destination AS route,
    p.passenger_name,
    p.age,
    t.fare,
    b.status,
    b.booking_date
FROM bookings b
JOIN trains t ON b.train_id = t.train_id
JOIN passengers p ON b.booking_id = p.booking_id
WHERE p.passenger_name LIKE '%neeva%';

/*
RESULT SET FOR QUERY 2:
+------------+-------------------------+-------------------------------------------------+----------------+-----+---------+-----------+---------------------+
| booking_id | train_name              | route                                           | passenger_name | age | fare    | status    | booking_date        |
+------------+-------------------------+-------------------------------------------------+----------------+-----+---------+-----------+---------------------+
| 102        | Mumbai Rajdhani Express | Mumbai Central (MMCT) -> Delhi Nizamuddin (NZM) | neeva mehta    | 27  | 2400.00 | CONFIRMED | 2026-10-29 05:04:02 |
+------------+-------------------------+-------------------------------------------------+----------------+-----+---------+-----------+---------------------+
*/

-- Query 3: Multi-Table Relational INNER JOIN (Full Ticket Manifest for all bookings)
SELECT 
    b.booking_id,
    t.train_name,
    t.source || ' -> ' || t.destination AS route,
    p.passenger_name,
    p.age,
    t.fare,
    b.status,
    b.booking_date
FROM bookings b
JOIN trains t ON b.train_id = t.train_id
JOIN passengers p ON b.booking_id = p.booking_id;

/*
RESULT SET FOR QUERY 3:
+------------+-------------------------+-------------------------------------------------+----------------+-----+---------+-----------+---------------------+
| booking_id | train_name              | route                                           | passenger_name | age | fare    | status    | booking_date        |
+------------+-------------------------+-------------------------------------------------+----------------+-----+---------+-----------+---------------------+
| 1          | Tejas Express           | Mumbai CSMT (CSMT) -> Goa Madgaon (MAO)         | heli           | 21  | 1580.00 | CONFIRMED | 2026-10-29 04:24:50 |
| 101        | Vande Bharat Express    | New Delhi (NDLS) -> Varanasi Junction (BSB)     | Heli Mehta     | 21  | 1750.00 | CONFIRMED | 2026-10-29 04:34:11 |
| 102        | Mumbai Rajdhani Express | Mumbai Central (MMCT) -> Delhi Nizamuddin (NZM) | neeva mehta    | 27  | 2400.00 | CONFIRMED | 2026-10-29 05:04:02 |
+------------+-------------------------+-------------------------------------------------+----------------+-----+---------+-----------+---------------------+
*/

-- Query 4: Querying directly from the SQL View (v_booking_manifest)
SELECT * FROM v_booking_manifest;
