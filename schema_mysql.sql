-- =======================================================
-- RAILWAY RESERVATION SYSTEM - MYSQL SCHEMA
-- Database: railway_db
-- =======================================================

CREATE DATABASE IF NOT EXISTS railway_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE railway_db;

-- 1. TABLES
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS trains (
    train_id INT PRIMARY KEY,
    train_name VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    fare DECIMAL(10, 2) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    train_id INT NOT NULL,
    booking_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('CONFIRMED', 'CANCELLED') DEFAULT 'CONFIRMED',
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
    FOREIGN KEY (train_id) REFERENCES trains(train_id) ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS passengers (
    passenger_id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    passenger_name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 2. INDEXES
CREATE INDEX idx_trains_route ON trains(source, destination);
CREATE INDEX idx_bookings_train ON bookings(train_id);
CREATE INDEX idx_passengers_booking ON passengers(booking_id);

-- 3. VIEWS
CREATE OR REPLACE VIEW v_booking_manifest AS
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

CREATE OR REPLACE VIEW v_train_occupancy_report AS
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

-- 4. TRIGGERS
DROP TRIGGER IF EXISTS trg_decrement_seat_on_booking;
DELIMITER //
CREATE TRIGGER trg_decrement_seat_on_booking
AFTER INSERT ON bookings
FOR EACH ROW
BEGIN
    IF NEW.status = 'CONFIRMED' THEN
        UPDATE trains 
        SET available_seats = available_seats - 1 
        WHERE train_id = NEW.train_id AND available_seats > 0;
    END IF;
END //
DELIMITER ;

DROP TRIGGER IF EXISTS trg_increment_seat_on_cancellation;
DELIMITER //
CREATE TRIGGER trg_increment_seat_on_cancellation
AFTER UPDATE ON bookings
FOR EACH ROW
BEGIN
    IF OLD.status = 'CONFIRMED' AND NEW.status = 'CANCELLED' THEN
        UPDATE trains 
        SET available_seats = LEAST(available_seats + 1, total_seats) 
        WHERE train_id = NEW.train_id;
    END IF;
END //
DELIMITER ;

-- 5. INITIAL MASTER DATA
INSERT IGNORE INTO trains (train_id, train_name, source, destination, total_seats, available_seats, fare)
VALUES 
(201, 'Vande Bharat Express', 'New Delhi (NDLS)', 'Varanasi Junction (BSB)', 50, 49, 1750.00),
(202, 'Mumbai Rajdhani Express', 'Mumbai Central (MMCT)', 'Delhi Nizamuddin (NZM)', 30, 29, 2400.00),
(203, 'Chennai Shatabdi Express', 'Bengaluru City (SBC)', 'Chennai Central (MAS)', 40, 39, 950.00),
(204, 'Tejas Express', 'Mumbai CSMT (CSMT)', 'Goa Madgaon (MAO)', 35, 34, 1580.00),
(205, 'Howrah Duronto Express', 'Kolkata Howrah (HWH)', 'New Delhi (NDLS)', 45, 45, 2200.00);

INSERT IGNORE INTO users (user_id, name, email)
VALUES (1, 'Heli Mehta', 'helimehta230@gmail.com');

-- 6. RECORDED RESERVATION DATA
INSERT IGNORE INTO bookings (booking_id, user_id, train_id, booking_date, status)
VALUES 
(1, 1, 204, '2026-10-29 04:24:50', 'CONFIRMED'),
(101, 1, 201, '2026-10-29 04:34:11', 'CONFIRMED'),
(102, 1, 202, '2026-10-29 05:04:02', 'CONFIRMED'),
(103, 1, 203, '2026-10-29 08:01:14', 'CONFIRMED');

INSERT IGNORE INTO passengers (passenger_id, booking_id, passenger_name, age)
VALUES 
(1, 1, 'heli', 21),
(501, 101, 'Heli Mehta', 21),
(502, 102, 'neeva mehta', 27),
(503, 103, 'neeva', 23);
