# database.py — Handles all database operations

import sqlite3
from datetime import datetime
import os
import hashlib
import hmac
from typing import Optional, List, Dict, Any

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

    # ── CLINICAL / HOSPITAL CORE ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT NOT NULL,
            department_id INTEGER,
            phone         TEXT,
            email         TEXT,
            active        INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS encounters (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  INTEGER NOT NULL,
            doctor_id   INTEGER,
            type        TEXT NOT NULL DEFAULT 'Outpatient', -- Outpatient/Inpatient/ER
            reason      TEXT,
            notes       TEXT,
            status      TEXT NOT NULL DEFAULT 'Open',       -- Open/Closed
            started_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            closed_at   TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id)  REFERENCES doctors(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vitals (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            encounter_id INTEGER NOT NULL,
            ts           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            temperature  REAL,
            pulse        INTEGER,
            systolic     INTEGER,
            diastolic    INTEGER,
            respiration  INTEGER,
            spo2         INTEGER,
            weight_kg    REAL,
            height_cm    REAL,
            FOREIGN KEY (encounter_id) REFERENCES encounters(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prescriptions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            encounter_id INTEGER NOT NULL,
            drug_name    TEXT NOT NULL,
            dosage       TEXT,
            frequency    TEXT,
            duration     TEXT,
            notes        TEXT,
            status       TEXT NOT NULL DEFAULT 'Active', -- Active/Stopped/Completed
            created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (encounter_id) REFERENCES encounters(id) ON DELETE CASCADE
        )
    """)

    # ── INVENTORY / PHARMACY ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            sku          TEXT UNIQUE,
            name         TEXT NOT NULL,
            category     TEXT,
            unit         TEXT DEFAULT 'unit',
            quantity     REAL NOT NULL DEFAULT 0,
            reorder_level REAL NOT NULL DEFAULT 0,
            updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_movements (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id   INTEGER NOT NULL,
            ts        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            qty_delta REAL NOT NULL,
            reason    TEXT,
            user_id   INTEGER,
            FOREIGN KEY (item_id) REFERENCES inventory_items(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── LAB ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_orders (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            encounter_id INTEGER NOT NULL,
            test_name    TEXT NOT NULL,
            priority     TEXT NOT NULL DEFAULT 'Routine', -- Routine/Urgent
            status       TEXT NOT NULL DEFAULT 'Ordered', -- Ordered/In Progress/Completed/Cancelled
            ordered_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (encounter_id) REFERENCES encounters(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lab_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL UNIQUE,
            result_text TEXT,
            reported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES lab_orders(id) ON DELETE CASCADE
        )
    """)

    # ── BILLING ──
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            code        TEXT UNIQUE,
            name        TEXT NOT NULL,
            category    TEXT,
            unit_price  REAL NOT NULL DEFAULT 0,
            active      INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  INTEGER NOT NULL,
            encounter_id INTEGER,
            status      TEXT NOT NULL DEFAULT 'Unpaid', -- Unpaid/Partially Paid/Paid/Void
            created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            notes       TEXT,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
            FOREIGN KEY (encounter_id) REFERENCES encounters(id) ON DELETE SET NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id  INTEGER NOT NULL,
            service_id  INTEGER,
            description TEXT NOT NULL,
            qty         REAL NOT NULL DEFAULT 1,
            unit_price  REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            amount     REAL NOT NULL,
            method     TEXT NOT NULL DEFAULT 'Cash',
            paid_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reference  TEXT,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_doctors_active       ON doctors(active);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_encounters_patient   ON encounters(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_encounters_status    ON encounters(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_patient     ON invoices(patient_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_name       ON inventory_items(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lab_orders_encounter ON lab_orders(encounter_id);")

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

def get_patient(patient_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE id = ? LIMIT 1", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return row

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

def get_patient_appointments(patient_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
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
        WHERE a.patient_id = ?
        ORDER BY a.date DESC, a.time DESC
        """,
        (patient_id,),
    )
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

# ── DEPARTMENTS / DOCTORS ──

def add_department(name: str) -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO departments (name) VALUES (?)", (name.strip(),))
    conn.commit()
    did = cursor.lastrowid
    conn.close()
    return did

def get_departments():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM departments ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_doctor(full_name: str, department_id: Optional[int] = None, phone: str = "", email: str = "") -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO doctors (full_name, department_id, phone, email, active)
        VALUES (?, ?, ?, ?, 1)
        """,
        (full_name.strip(), department_id, phone.strip() or None, email.strip() or None),
    )
    conn.commit()
    did = cursor.lastrowid
    conn.close()
    return did

def get_doctors(active_only: bool = True):
    conn = connect()
    cursor = conn.cursor()
    if active_only:
        cursor.execute(
            """
            SELECT d.id, d.full_name, COALESCE(dep.name,''), d.phone, d.email, d.active
            FROM doctors d
            LEFT JOIN departments dep ON dep.id = d.department_id
            WHERE d.active = 1
            ORDER BY d.full_name
            """
        )
    else:
        cursor.execute(
            """
            SELECT d.id, d.full_name, COALESCE(dep.name,''), d.phone, d.email, d.active
            FROM doctors d
            LEFT JOIN departments dep ON dep.id = d.department_id
            ORDER BY d.full_name
            """
        )
    rows = cursor.fetchall()
    conn.close()
    return rows

def set_doctor_active(doctor_id: int, active: bool):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE doctors SET active = ? WHERE id = ?", (1 if active else 0, doctor_id))
    conn.commit()
    conn.close()

# ── ENCOUNTERS / VITALS ──

def add_encounter(patient_id: int, doctor_id: Optional[int], enc_type: str, reason: str = "", notes: str = "") -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO encounters (patient_id, doctor_id, type, reason, notes, status)
        VALUES (?, ?, ?, ?, ?, 'Open')
        """,
        (patient_id, doctor_id, enc_type, reason.strip() or None, notes.strip() or None),
    )
    conn.commit()
    eid = cursor.lastrowid
    conn.close()
    return eid

def close_encounter(encounter_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE encounters SET status='Closed', closed_at=CURRENT_TIMESTAMP WHERE id = ?", (encounter_id,))
    conn.commit()
    conn.close()

def get_patient_encounters(patient_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT e.id, e.type, COALESCE(d.full_name,''), e.reason, e.status, e.started_at, COALESCE(e.closed_at,'')
        FROM encounters e
        LEFT JOIN doctors d ON d.id = e.doctor_id
        WHERE e.patient_id = ?
        ORDER BY e.started_at DESC
        """,
        (patient_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_encounters(status: Optional[str] = None):
    conn = connect()
    cursor = conn.cursor()
    if status:
        cursor.execute(
            """
            SELECT e.id, p.name, COALESCE(d.full_name,''), e.type, COALESCE(e.reason,''), e.status, e.started_at
            FROM encounters e
            JOIN patients p ON p.id = e.patient_id
            LEFT JOIN doctors d ON d.id = e.doctor_id
            WHERE e.status = ?
            ORDER BY e.started_at DESC
            """,
            (status,),
        )
    else:
        cursor.execute(
            """
            SELECT e.id, p.name, COALESCE(d.full_name,''), e.type, COALESCE(e.reason,''), e.status, e.started_at
            FROM encounters e
            JOIN patients p ON p.id = e.patient_id
            LEFT JOIN doctors d ON d.id = e.doctor_id
            ORDER BY e.started_at DESC
            """
        )
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_vitals(encounter_id: int, temperature=None, pulse=None, systolic=None, diastolic=None, respiration=None, spo2=None, weight_kg=None, height_cm=None):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vitals (encounter_id, temperature, pulse, systolic, diastolic, respiration, spo2, weight_kg, height_cm)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (encounter_id, temperature, pulse, systolic, diastolic, respiration, spo2, weight_kg, height_cm),
    )
    conn.commit()
    conn.close()

def get_encounter_vitals(encounter_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ts, temperature, pulse, systolic, diastolic, respiration, spo2, weight_kg, height_cm
        FROM vitals
        WHERE encounter_id = ?
        ORDER BY ts DESC
        """,
        (encounter_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# ── PRESCRIPTIONS ──

def add_prescription(encounter_id: int, drug_name: str, dosage: str = "", frequency: str = "", duration: str = "", notes: str = "") -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO prescriptions (encounter_id, drug_name, dosage, frequency, duration, notes, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Active')
        """,
        (encounter_id, drug_name.strip(), dosage.strip() or None, frequency.strip() or None, duration.strip() or None, notes.strip() or None),
    )
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return pid

def get_encounter_prescriptions(encounter_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, drug_name, dosage, frequency, duration, status, created_at
        FROM prescriptions
        WHERE encounter_id = ?
        ORDER BY created_at DESC
        """,
        (encounter_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

# ── LAB ──

def add_lab_order(encounter_id: int, test_name: str, priority: str = "Routine") -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO lab_orders (encounter_id, test_name, priority, status) VALUES (?, ?, ?, 'Ordered')",
        (encounter_id, test_name.strip(), priority),
    )
    conn.commit()
    oid = cursor.lastrowid
    conn.close()
    return oid

def get_encounter_lab_orders(encounter_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT o.id, o.test_name, o.priority, o.status, o.ordered_at, COALESCE(r.result_text,'')
        FROM lab_orders o
        LEFT JOIN lab_results r ON r.order_id = o.id
        WHERE o.encounter_id = ?
        ORDER BY o.ordered_at DESC
        """,
        (encounter_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def set_lab_result(order_id: int, result_text: str):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE lab_orders SET status='Completed' WHERE id = ?", (order_id,))
    cursor.execute(
        """
        INSERT INTO lab_results (order_id, result_text)
        VALUES (?, ?)
        ON CONFLICT(order_id) DO UPDATE SET result_text=excluded.result_text, reported_at=CURRENT_TIMESTAMP
        """,
        (order_id, result_text),
    )
    conn.commit()
    conn.close()

# ── INVENTORY ──

def add_inventory_item(name: str, sku: str = "", category: str = "", unit: str = "unit", quantity: float = 0, reorder_level: float = 0) -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO inventory_items (sku, name, category, unit, quantity, reorder_level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sku.strip() or None, name.strip(), category.strip() or None, unit.strip() or "unit", float(quantity), float(reorder_level)),
    )
    conn.commit()
    iid = cursor.lastrowid
    conn.close()
    return iid

def get_inventory_items():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, COALESCE(sku,''), name, COALESCE(category,''), unit, quantity, reorder_level, updated_at FROM inventory_items ORDER BY name"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_low_stock_items():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, COALESCE(sku,''), name, COALESCE(category,''), unit, quantity, reorder_level
        FROM inventory_items
        WHERE quantity <= reorder_level
        ORDER BY name
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def adjust_inventory(item_id: int, qty_delta: float, reason: str = "", user_id: Optional[int] = None):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE inventory_items SET quantity = quantity + ?, updated_at=CURRENT_TIMESTAMP WHERE id = ?", (qty_delta, item_id))
    cursor.execute(
        "INSERT INTO inventory_movements (item_id, qty_delta, reason, user_id) VALUES (?, ?, ?, ?)",
        (item_id, qty_delta, reason.strip() or None, user_id),
    )
    conn.commit()
    conn.close()

# ── BILLING ──

def add_service(name: str, unit_price: float, code: str = "", category: str = "") -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO services (code, name, category, unit_price, active) VALUES (?, ?, ?, ?, 1)",
        (code.strip() or None, name.strip(), category.strip() or None, float(unit_price)),
    )
    conn.commit()
    sid = cursor.lastrowid
    conn.close()
    return sid

def get_services(active_only: bool = True):
    conn = connect()
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT id, COALESCE(code,''), name, COALESCE(category,''), unit_price, active FROM services WHERE active=1 ORDER BY name")
    else:
        cursor.execute("SELECT id, COALESCE(code,''), name, COALESCE(category,''), unit_price, active FROM services ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_invoice(patient_id: int, encounter_id: Optional[int] = None, notes: str = "") -> int:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO invoices (patient_id, encounter_id, status, notes) VALUES (?, ?, 'Unpaid', ?)",
        (patient_id, encounter_id, notes.strip() or None),
    )
    conn.commit()
    iid = cursor.lastrowid
    conn.close()
    return iid

def add_invoice_item(invoice_id: int, description: str, qty: float, unit_price: float, service_id: Optional[int] = None):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO invoice_items (invoice_id, service_id, description, qty, unit_price)
        VALUES (?, ?, ?, ?, ?)
        """,
        (invoice_id, service_id, description.strip(), float(qty), float(unit_price)),
    )
    conn.commit()
    conn.close()

def get_patient_invoices(patient_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.id, i.status, i.created_at,
               COALESCE((SELECT SUM(qty*unit_price) FROM invoice_items it WHERE it.invoice_id=i.id),0) AS total,
               COALESCE((SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.id),0) AS paid
        FROM invoices i
        WHERE i.patient_id = ?
        ORDER BY i.created_at DESC
        """,
        (patient_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_invoices():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.id, p.name, i.status, i.created_at,
               COALESCE((SELECT SUM(qty*unit_price) FROM invoice_items it WHERE it.invoice_id=i.id),0) AS total,
               COALESCE((SELECT SUM(amount) FROM payments p2 WHERE p2.invoice_id=i.id),0) AS paid
        FROM invoices i
        JOIN patients p ON p.id = i.patient_id
        ORDER BY i.created_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_lab_orders():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT o.id, p.name, o.test_name, o.priority, o.status, o.ordered_at
        FROM lab_orders o
        JOIN encounters e ON e.id = o.encounter_id
        JOIN patients p ON p.id = e.patient_id
        ORDER BY o.ordered_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_invoice_items(invoice_id: int):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, description, qty, unit_price, (qty*unit_price) FROM invoice_items WHERE invoice_id=?",
        (invoice_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_payment(invoice_id: int, amount: float, method: str = "Cash", reference: str = ""):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO payments (invoice_id, amount, method, reference) VALUES (?, ?, ?, ?)",
        (invoice_id, float(amount), method, reference.strip() or None),
    )
    # Update invoice status
    cursor.execute("SELECT COALESCE(SUM(qty*unit_price),0) FROM invoice_items WHERE invoice_id=?", (invoice_id,))
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?", (invoice_id,))
    paid = cursor.fetchone()[0]
    status = "Paid" if paid >= total and total > 0 else ("Partially Paid" if paid > 0 else "Unpaid")
    cursor.execute("UPDATE invoices SET status=? WHERE id=?", (status, invoice_id))
    conn.commit()
    conn.close()
