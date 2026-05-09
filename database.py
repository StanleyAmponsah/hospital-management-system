# database.py — Handles all database operations

import sqlite3
from datetime import datetime
import os
import hashlib
import hmac

DB_NAME = "hospital.db"

def connect():
    conn = sqlite3.connect(DB_NAME)
    # SQLite does not enforce FOREIGN KEY constraints unless enabled per connection.
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def initialize_db():
    """Create tables if they don't exist."""
    conn = connect()
    cursor = conn.cursor()

    # ── AUTH / USERS ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            full_name     TEXT,
            role          TEXT NOT NULL,
            password_hash BLOB NOT NULL,
            salt          BLOB NOT NULL,
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id     INTEGER,
            username    TEXT,
            action      TEXT NOT NULL,
            entity_type TEXT,
            entity_id   INTEGER,
            details     TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

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
            doctor       TEXT NOT NULL,
            date         TEXT NOT NULL,
            time         TEXT NOT NULL,
            notes        TEXT,
            status       TEXT DEFAULT 'Scheduled',
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        )
    """)

    # ── Migration: older versions stored patient_name in appointments ──
    # If the column exists, rebuild the table without it (patient name is derived via JOIN).
    cursor.execute("PRAGMA table_info(appointments)")
    appt_cols = {row[1] for row in cursor.fetchall()}  # row[1] is column name
    if "patient_name" in appt_cols:
        # Temporarily disable foreign key checks during the table rebuild.
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("ALTER TABLE appointments RENAME TO appointments_old;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id   INTEGER NOT NULL,
                doctor       TEXT NOT NULL,
                date         TEXT NOT NULL,
                time         TEXT NOT NULL,
                notes        TEXT,
                status       TEXT DEFAULT 'Scheduled',
                FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            INSERT INTO appointments (id, patient_id, doctor, date, time, notes, status)
            SELECT id, patient_id, doctor, date, time, notes, status
            FROM appointments_old
        """)
        cursor.execute("DROP TABLE appointments_old;")
        cursor.execute("PRAGMA foreign_keys = ON;")

    # ── Indexes for common lookups ──
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_registered ON patients(registered);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_status     ON patients(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_name       ON patients(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date    ON appointments(date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_pid     ON appointments(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username       ON users(username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts             ON audit_log(ts);")

    conn.commit()

    # Bootstrap a default admin if there are no users yet.
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    if user_count == 0:
        create_user(
            username="admin",
            password="admin123",
            role="Admin",
            full_name="System Administrator",
            created_by_user=None,
        )

    conn.close()

# ── PASSWORDS / AUTH ──

def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)

def create_user(username: str, password: str, role: str, full_name: str = "", created_by_user=None):
    salt = os.urandom(16)
    pw_hash = _hash_password(password, salt)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (username, full_name, role, password_hash, salt, active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (username.strip(), full_name.strip() if full_name else None, role, pw_hash, salt),
    )
    uid = cursor.lastrowid
    conn.commit()
    conn.close()
    if created_by_user:
        log_audit(
            user_id=created_by_user["id"],
            username=created_by_user["username"],
            action="CREATE_USER",
            entity_type="users",
            entity_id=uid,
            details=f"Created user '{username}' with role '{role}'",
        )
    return uid

def get_users():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, role, active, created_at FROM users ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def authenticate(username: str, password: str):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, full_name, role, password_hash, salt, active
        FROM users
        WHERE username = ?
        """,
        (username.strip(),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    uid, uname, full_name, role, pw_hash, salt, active = row
    if not active:
        return None
    candidate = _hash_password(password, salt)
    if not hmac.compare_digest(pw_hash, candidate):
        return None
    return {"id": uid, "username": uname, "full_name": full_name or "", "role": role}

def set_user_password(user_id: int, new_password: str, changed_by_user=None):
    salt = os.urandom(16)
    pw_hash = _hash_password(new_password, salt)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (pw_hash, salt, user_id))
    conn.commit()
    conn.close()
    if changed_by_user:
        log_audit(
            user_id=changed_by_user["id"],
            username=changed_by_user["username"],
            action="RESET_PASSWORD",
            entity_type="users",
            entity_id=user_id,
            details="Password reset",
        )

def set_user_active(user_id: int, active: bool, changed_by_user=None):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))
    conn.commit()
    conn.close()
    if changed_by_user:
        log_audit(
            user_id=changed_by_user["id"],
            username=changed_by_user["username"],
            action="SET_USER_ACTIVE",
            entity_type="users",
            entity_id=user_id,
            details=f"Set active={bool(active)}",
        )

# ── AUDIT LOG ──

def log_audit(user_id, username, action, entity_type=None, entity_id=None, details=None):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO audit_log (user_id, username, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, username, action, entity_type, entity_id, details),
    )
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
    cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()

# ── SINGLE-PATIENT HELPERS ──

def patient_exists(patient_id: int) -> bool:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM patients WHERE id = ? LIMIT 1", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def get_patient_name(patient_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM patients WHERE id = ? LIMIT 1", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# ── APPOINTMENT OPERATIONS ──

def add_appointment(patient_id, doctor, date, time, notes=""):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO appointments (patient_id, doctor, date, time, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (patient_id, doctor, date, time, notes))
    conn.commit()
    conn.close()

def get_all_appointments():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            a.id,
            a.patient_id,
            p.name AS patient_name,
            a.doctor,
            a.date,
            a.time,
            a.notes,
            a.status
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        ORDER BY a.date DESC, a.time DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_today_appointments():
    today = datetime.now().strftime("%Y-%m-%d")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            a.id,
            a.patient_id,
            p.name AS patient_name,
            a.doctor,
            a.date,
            a.time,
            a.notes,
            a.status
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.date = ?
    """, (today,))
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
