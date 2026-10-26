PRAGMA foreign_keys = ON;

-- Re-create tables cleanly
DROP TABLE IF EXISTS passengers;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS trains;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL
);

CREATE TABLE trains (
    train_id INTEGER PRIMARY KEY,
    train_name TEXT NOT NULL,
    source TEXT NOT NULL,
    destination TEXT NOT NULL,
    total_seats INTEGER NOT NULL,
    available_seats INTEGER NOT NULL,
    fare REAL NOT NULL
);

CREATE TABLE bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    train_id INTEGER NOT NULL,
    booking_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'CONFIRMED',
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (train_id) REFERENCES trains(train_id)
);

CREATE TABLE passengers (
    passenger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    passenger_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
);

-- Insert Indian Railways Routes
INSERT INTO trains (train_id, train_name, source, destination, total_seats, available_seats, fare)
VALUES 
(201, 'Vande Bharat Express', 'New Delhi (NDLS)', 'Varanasi Junction (BSB)', 50, 50, 1750.00),
(202, 'Mumbai Rajdhani Express', 'Mumbai Central (MMCT)', 'Delhi Nizamuddin (NZM)', 30, 30, 2400.00),
(203, 'Chennai Shatabdi Express', 'Bengaluru City (SBC)', 'Chennai Central (MAS)', 40, 40, 950.00),
(204, 'Tejas Express', 'Mumbai CSMT (CSMT)', 'Goa Madgaon (MAO)', 35, 35, 1580.00),
(205, 'Howrah Duronto Express', 'Kolkata Howrah (HWH)', 'New Delhi (NDLS)', 45, 45, 2200.00);

INSERT INTO users (user_id, name, email)
VALUES (1, 'Default Student', 'student@example.com');