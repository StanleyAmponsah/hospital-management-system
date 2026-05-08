# database.py — Handles all database operations

import sqlite3
from datetime import datetime

DB_NAME = "hospital.db"

def connect():
    return sqlite3.connect(DB_NAME)

def initialize_db():
    """Create tables if they don't exist."""
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            age         INTEGER NOT NULL,
            gender      TEXT NOT NULL,
            contact     TEXT NOT NULL,
            condition   TEXT NOT NULL,
            status      TEXT DEFAULT 'Active',
            registered  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER NOT NULL,
            patient_name TEXT NOT NULL,
            doctor       TEXT NOT NULL,
            date         TEXT NOT NULL,
            time         TEXT NOT NULL,
            notes        TEXT,
            status       TEXT DEFAULT 'Scheduled',
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    conn.commit()
    conn.close()

# ── PATIENT OPERATIONS ──

def add_patient(name, age, gender, contact, condition):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO patients (name, age, gender, contact, condition)
        VALUES (?, ?, ?, ?, ?)
    """, (name, age, gender, contact, condition))
    conn.commit()
    patient_id = cursor.lastrowid
    conn.close()
    return patient_id

def get_all_patients():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients ORDER BY registered DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_active_patients():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE status = 'Active' ORDER BY registered DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_patients(query):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM patients
        WHERE name LIKE ? OR CAST(id AS TEXT) LIKE ?
        ORDER BY registered DESC
    """, (f"%{query}%", f"%{query}%"))
    rows = cursor.fetchall()
    conn.close()
    return rows

def discharge_patient(patient_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE patients SET status = 'Discharged' WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()

def delete_patient(patient_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE patient_id = ?", (patient_id,))
    cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()

# ── APPOINTMENT OPERATIONS ──

def add_appointment(patient_id, patient_name, doctor, date, time, notes=""):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (patient_id, patient_name, doctor, date, time, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (patient_id, patient_name, doctor, date, time, notes))
    conn.commit()
    conn.close()

def get_all_appointments():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments ORDER BY date DESC, time DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_today_appointments():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointments WHERE date = ?", (today,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def cancel_appointment(appointment_id):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = 'Cancelled' WHERE id = ?", (appointment_id,))
    conn.commit()
    conn.close()

# ── DASHBOARD STATS ──

def get_stats():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM patients")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM patients WHERE status = 'Active'")
    active = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM patients WHERE status = 'Discharged'")
    discharged = cursor.fetchone()[0]
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE date = ?", (today,))
    today_appts = cursor.fetchone()[0]
    conn.close()
    return {
        "total": total,
        "active": active,
        "discharged": discharged,
        "today_appointments": today_appts
    }
