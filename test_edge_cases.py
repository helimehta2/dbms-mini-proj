"""
DBMS Edge Cases Verification Test Suite
Tests:
1. Concurrent Simultaneous Booking (Race Condition & Overbooking Guard)
2. Double Cancellation (Idempotency & Seat Inflation Guard)
3. Partial Failure & Crash Recovery (ACID Atomicity & Rollback Verification)
"""

import sqlite3
import concurrent.futures
import os
import sys

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DB_NAME = "railway.db"

def reset_db():
    if os.path.exists(DB_NAME):
        try:
            os.remove(DB_NAME)
        except PermissionError:
            pass
    import app
    app.init_db()

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=15.0, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def test_edge_case_1_concurrency():
    print("\n" + "="*60)
    print("TEST 1: CONCURRENCY / RACE CONDITION (Two users booking last seat)")
    print("="*60)
    reset_db()
    conn = get_db()
    
    # Force Train 201 to have ONLY 1 remaining seat
    conn.execute("UPDATE trains SET available_seats = 1 WHERE train_id = 201")
    conn.close()

    results = []

    def attempt_booking(user_name):
        c = get_db()
        cur = c.cursor()
        success = False
        message = ""
        try:
            c.execute("BEGIN IMMEDIATE")
            cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
            seats = cur.fetchone()[0]
            if seats <= 0:
                c.execute("ROLLBACK")
                message = "Rejected: Sold out (0 seats)"
            else:
                cur.execute("INSERT INTO bookings (user_id, train_id) VALUES (1, 201)")
                bid = cur.lastrowid
                cur.execute("INSERT INTO passengers (booking_id, passenger_name, age) VALUES (?, ?, 21)", (bid, user_name))
                c.execute("COMMIT")
                success = True
                message = f"Success: Reserved booking #{bid}"
        except Exception as e:
            try:
                c.execute("ROLLBACK")
            except:
                pass
            message = f"Rejected by DB trigger: {e}"
        finally:
            c.close()
        return (user_name, success, message)

    # Launch two concurrent booking threads at the exact same time
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_booking, "Passenger Alice")
        f2 = executor.submit(attempt_booking, "Passenger Bob")
        results = [f1.result(), f2.result()]

    for user, success, msg in results:
        status_tag = "[BOOKED]" if success else "[REJECTED]"
        print(f"  {status_tag} {user}: {msg}")

    # Check final seats in database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    final_seats = cur.fetchone()[0]
    conn.close()

    successes = sum(1 for r in results if r[1])
    rejections = sum(1 for r in results if not r[1])

    print(f"\n  Final available seats in database: {final_seats}")
    assert successes == 1, f"Expected exactly 1 success, got {successes}"
    assert rejections == 1, f"Expected exactly 1 rejection, got {rejections}"
    assert final_seats == 0, f"Expected 0 seats, got {final_seats} (Overbooking occurred!)"
    print("  >>> RESULT: PASS! Exactly 1 user booked; 1 user safely rejected. Overbooking PREVENTED.")


def test_edge_case_2_double_cancellation():
    print("\n" + "="*60)
    print("TEST 2: DOUBLE CANCELLATION (Preventing Seat Inflation)")
    print("="*60)
    reset_db()
    conn = get_db()
    cur = conn.cursor()

    # Initial seats: 50
    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    initial_seats = cur.fetchone()[0]
    print(f"  1. Initial available seats: {initial_seats}")

    # Book 1 ticket
    conn.execute("BEGIN IMMEDIATE")
    cur.execute("INSERT INTO bookings (user_id, train_id) VALUES (1, 201)")
    bid = cur.lastrowid
    cur.execute("INSERT INTO passengers (booking_id, passenger_name, age) VALUES (?, 'Test Passenger', 25)", (bid,))
    conn.execute("COMMIT")

    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    booked_seats = cur.fetchone()[0]
    print(f"  2. After booking: seats = {booked_seats} (Decremented by trigger)")

    # Cancel First Time
    conn.execute("BEGIN IMMEDIATE")
    cur.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = ? AND status = 'CONFIRMED'", (bid,))
    first_cancel_rowcount = cur.rowcount
    conn.execute("COMMIT")

    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    seats_after_cancel1 = cur.fetchone()[0]
    print(f"  3. First Cancellation: {first_cancel_rowcount} row updated. Seats restored to {seats_after_cancel1}")

    # Cancel Second Time (Attempting to exploit / duplicate cancellation)
    conn.execute("BEGIN IMMEDIATE")
    cur.execute("UPDATE bookings SET status = 'CANCELLED' WHERE booking_id = ? AND status = 'CONFIRMED'", (bid,))
    second_cancel_rowcount = cur.rowcount
    conn.execute("ROLLBACK" if second_cancel_rowcount == 0 else "COMMIT")

    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    seats_after_cancel2 = cur.fetchone()[0]
    print(f"  4. Second Cancellation Attempt: {second_cancel_rowcount} rows affected (REJECTED)")
    print(f"     Final available seats: {seats_after_cancel2}")

    conn.close()

    assert first_cancel_rowcount == 1, "First cancellation should affect 1 row"
    assert second_cancel_rowcount == 0, "Second cancellation must affect 0 rows"
    assert seats_after_cancel2 == initial_seats, f"Seats inflated! Expected {initial_seats}, got {seats_after_cancel2}"
    print("  >>> RESULT: PASS! Double cancellation blocked; seats were NOT falsely inflated.")


def test_edge_case_3_atomicity_rollback():
    print("\n" + "="*60)
    print("TEST 3: ACID ATOMICITY & PARTIAL CRASH RECOVERY")
    print("="*60)
    reset_db()
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    seats_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bookings")
    bookings_before = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM passengers")
    passengers_before = cur.fetchone()[0]

    print(f"  Before Attempt: {seats_before} seats, {bookings_before} bookings, {passengers_before} passengers.")

    # Simulate an error midway: Valid booking insert, but invalid passenger age (exceeds CHECK constraint: age <= 120)
    print("  Attempting booking with invalid passenger age (age = 999 violates CHECK constraint)...")
    transaction_failed = False
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur.execute("INSERT INTO bookings (user_id, train_id) VALUES (1, 201)")
        bid = cur.lastrowid
        # This will fail due to CHECK (age > 0 AND age <= 120)
        cur.execute("INSERT INTO passengers (booking_id, passenger_name, age) VALUES (?, 'Invalid Age Guy', 999)", (bid,))
        conn.execute("COMMIT")
    except Exception as e:
        transaction_failed = True
        conn.execute("ROLLBACK")
        print(f"  Caught expected database exception: {e}")
        print("  Executing conn.execute('ROLLBACK')...")

    cur.execute("SELECT available_seats FROM trains WHERE train_id = 201")
    seats_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM bookings")
    bookings_after = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM passengers")
    passengers_after = cur.fetchone()[0]

    conn.close()

    print(f"  After Rollback: {seats_after} seats, {bookings_after} bookings, {passengers_after} passengers.")
    assert transaction_failed, "Transaction should have failed on invalid age"
    assert seats_after == seats_before, "Seat count should be unchanged"
    assert bookings_after == bookings_before, "No partial booking should exist"
    assert passengers_after == passengers_before, "No partial passenger should exist"
    print("  >>> RESULT: PASS! Full rollback verified. No orphaned or partial data.")

if __name__ == "__main__":
    test_edge_case_1_concurrency()
    test_edge_case_2_double_cancellation()
    test_edge_case_3_atomicity_rollback()
    print("\n" + "="*60)
    print("ALL 3 DBMS EDGE CASES VERIFIED AND PASSED SUCCESSFULLY!")
    print("="*60 + "\n")
