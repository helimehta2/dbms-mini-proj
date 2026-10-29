import pymysql

def setup_mysql():
    print("Connecting to MySQL server on localhost:3306...")
    conn = pymysql.connect(host="localhost", user="root", password="", port=3306)
    cur = conn.cursor()

    # 1. Create user 'heli' matching MySQL Workbench connection
    try:
        cur.execute("CREATE USER IF NOT EXISTS 'heli'@'localhost' IDENTIFIED BY '';")
        cur.execute("CREATE USER IF NOT EXISTS 'heli'@'%' IDENTIFIED BY '';")
        cur.execute("GRANT ALL PRIVILEGES ON *.* TO 'heli'@'localhost' WITH GRANT OPTION;")
        cur.execute("GRANT ALL PRIVILEGES ON *.* TO 'heli'@'%' WITH GRANT OPTION;")
        cur.execute("FLUSH PRIVILEGES;")
        print("-> User 'heli' configured with full access!")
    except Exception as e:
        print(f"User config note: {e}")

    # 2. Create database 'railway_db'
    cur.execute("CREATE DATABASE IF NOT EXISTS railway_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
    cur.execute("USE railway_db;")
    print("-> Database 'railway_db' active!")

    # 3. Create Tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL
    ) ENGINE=InnoDB;
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS trains (
        train_id INT PRIMARY KEY,
        train_name VARCHAR(100) NOT NULL,
        source VARCHAR(100) NOT NULL,
        destination VARCHAR(100) NOT NULL,
        total_seats INT NOT NULL,
        available_seats INT NOT NULL,
        fare DECIMAL(10, 2) NOT NULL
    ) ENGINE=InnoDB;
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        booking_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        train_id INT NOT NULL,
        booking_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        status ENUM('CONFIRMED', 'CANCELLED') DEFAULT 'CONFIRMED',
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE RESTRICT,
        FOREIGN KEY (train_id) REFERENCES trains(train_id) ON DELETE RESTRICT
    ) ENGINE=InnoDB;
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS passengers (
        passenger_id INT AUTO_INCREMENT PRIMARY KEY,
        booking_id INT NOT NULL,
        passenger_name VARCHAR(100) NOT NULL,
        age INT NOT NULL,
        FOREIGN KEY (booking_id) REFERENCES bookings(booking_id) ON DELETE CASCADE
    ) ENGINE=InnoDB;
    """)
    print("-> Tables (users, trains, bookings, passengers) created!")

    # 4. Create Indexes
    try:
        cur.execute("CREATE INDEX idx_trains_route ON trains(source, destination);")
    except:
        pass
    try:
        cur.execute("CREATE INDEX idx_bookings_train ON bookings(train_id);")
    except:
        pass
    try:
        cur.execute("CREATE INDEX idx_passengers_booking ON passengers(booking_id);")
    except:
        pass
    print("-> Indexes created!")

    # 5. Create Views
    cur.execute("DROP VIEW IF EXISTS v_booking_manifest;")
    cur.execute("""
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
    """)

    cur.execute("DROP VIEW IF EXISTS v_train_occupancy_report;")
    cur.execute("""
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
    """)
    print("-> Views (v_booking_manifest, v_train_occupancy_report) created!")

    # 6. Create Triggers
    cur.execute("DROP TRIGGER IF EXISTS trg_decrement_seat_on_booking;")
    cur.execute("""
    CREATE TRIGGER trg_decrement_seat_on_booking
    AFTER INSERT ON bookings
    FOR EACH ROW
    BEGIN
        IF NEW.status = 'CONFIRMED' THEN
            UPDATE trains 
            SET available_seats = available_seats - 1 
            WHERE train_id = NEW.train_id AND available_seats > 0;
        END IF;
    END;
    """)

    cur.execute("DROP TRIGGER IF EXISTS trg_increment_seat_on_cancellation;")
    cur.execute("""
    CREATE TRIGGER trg_increment_seat_on_cancellation
    AFTER UPDATE ON bookings
    FOR EACH ROW
    BEGIN
        IF OLD.status = 'CONFIRMED' AND NEW.status = 'CANCELLED' THEN
            UPDATE trains 
            SET available_seats = LEAST(available_seats + 1, total_seats) 
            WHERE train_id = NEW.train_id;
        END IF;
    END;
    """)
    print("-> Triggers configured!")

    # 7. Seed Trains & User
    cur.execute("""
    INSERT IGNORE INTO trains (train_id, train_name, source, destination, total_seats, available_seats, fare)
    VALUES 
    (201, 'Vande Bharat Express', 'New Delhi (NDLS)', 'Varanasi Junction (BSB)', 50, 49, 1750.00),
    (202, 'Mumbai Rajdhani Express', 'Mumbai Central (MMCT)', 'Delhi Nizamuddin (NZM)', 30, 29, 2400.00),
    (203, 'Chennai Shatabdi Express', 'Bengaluru City (SBC)', 'Chennai Central (MAS)', 40, 39, 950.00),
    (204, 'Tejas Express', 'Mumbai CSMT (CSMT)', 'Goa Madgaon (MAO)', 35, 34, 1580.00),
    (205, 'Howrah Duronto Express', 'Kolkata Howrah (HWH)', 'New Delhi (NDLS)', 45, 45, 2200.00);
    """)

    cur.execute("""
    INSERT IGNORE INTO users (user_id, name, email)
    VALUES (1, 'Heli Mehta', 'helimehta230@gmail.com');
    """)

    # 8. Seed All Existing Reservations
    cur.execute("""
    INSERT IGNORE INTO bookings (booking_id, user_id, train_id, booking_date, status)
    VALUES 
    (1, 1, 204, '2026-10-29 04:24:50', 'CONFIRMED'),
    (101, 1, 201, '2026-10-29 04:34:11', 'CONFIRMED'),
    (102, 1, 202, '2026-10-29 05:04:02', 'CONFIRMED'),
    (103, 1, 203, '2026-10-29 08:01:14', 'CONFIRMED');
    """)

    cur.execute("""
    INSERT IGNORE INTO passengers (passenger_id, booking_id, passenger_name, age)
    VALUES 
    (1, 1, 'heli', 21),
    (501, 101, 'Heli Mehta', 21),
    (502, 102, 'neeva mehta', 27),
    (503, 103, 'neeva', 23);
    """)

    conn.commit()
    conn.close()
    print("\nSUCCESS: MYSQL DATABASE 'railway_db' FULLY SETUP AND LOADED!")

if __name__ == "__main__":
    setup_mysql()
