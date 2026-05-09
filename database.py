# database.py — Handles all database operations

import sqlite3
from datetime import datetime
import os
import re
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
            login_id      INTEGER UNIQUE,
            doctor_id     INTEGER,
            email         TEXT NOT NULL DEFAULT '',
            phone         TEXT NOT NULL DEFAULT '',
            must_change_password INTEGER NOT NULL DEFAULT 0,
            password_hash BLOB NOT NULL,
            salt          BLOB NOT NULL,
            active        INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
    """)

    # ── Migration: add login_id / doctor_id / contact / first-login flag ──
    cursor.execute("PRAGMA table_info(users)")
    user_cols = {row[1] for row in cursor.fetchall()}
    if "login_id" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN login_id INTEGER;")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login_id ON users(login_id);")
    if "doctor_id" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN doctor_id INTEGER;")
    if "email" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT '';")
    if "phone" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT '';")
    if "must_change_password" not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;")

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
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            ts                   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            role                 TEXT NOT NULL,
            login_id             INTEGER NOT NULL,
            notes                TEXT,
            status               TEXT NOT NULL DEFAULT 'pending',
            resolved_ts          TEXT,
            resolved_by_user_id  INTEGER,
            matched_user_id      INTEGER,
            FOREIGN KEY (matched_user_id) REFERENCES users(id),
            FOREIGN KEY (resolved_by_user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL,
            age                 INTEGER NOT NULL,
            gender              TEXT NOT NULL,
            contact             TEXT NOT NULL,
            condition           TEXT NOT NULL,
            status              TEXT DEFAULT 'Active',
            registered          TEXT DEFAULT CURRENT_TIMESTAMP,
            hospital_card_number TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(patients)")
    patient_cols = {row[1] for row in cursor.fetchall()}
    if "hospital_card_number" not in patient_cols:
        cursor.execute("ALTER TABLE patients ADD COLUMN hospital_card_number TEXT;")

    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_hospital_card ON patients(hospital_card_number)"
    )

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
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login_id ON users(login_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts             ON audit_log(ts);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pwreset_status       ON password_reset_requests(status);")
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
            login_id=1,
            email="",
            phone="",
            must_change_password=False,
            created_by_user=None,
        )

    # Legacy DBs: every account must have a unique numeric staff login_id.
    cursor.execute("SELECT id FROM users WHERE login_id IS NULL ORDER BY id")
    missing_ids = [row[0] for row in cursor.fetchall()]
    if missing_ids:
        cursor.execute("SELECT COALESCE(MAX(login_id), 0) FROM users WHERE login_id IS NOT NULL")
        nxt = int(cursor.fetchone()[0]) + 1
        for uid in missing_ids:
            cursor.execute("UPDATE users SET login_id = ? WHERE id = ?", (nxt, uid))
            nxt += 1
        conn.commit()

    conn.close()

# ── PASSWORDS / AUTH ──

def _hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)


def count_registered_staff(active_only: bool = True) -> int:
    """Hospital staff only — excludes system Administrator accounts."""
    conn = connect()
    cursor = conn.cursor()
    if active_only:
        cursor.execute("SELECT COUNT(*) FROM users WHERE active = 1 AND role != 'Admin'")
    else:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role != 'Admin'")
    n = cursor.fetchone()[0]
    conn.close()
    return int(n)


def generate_unique_staff_username(role: str, login_id: Optional[int], full_name: str = "") -> str:
    """Internal username slug for audit/UI; staff always sign in with login_id + password."""
    conn = connect()
    cursor = conn.cursor()

    def taken(u: str) -> bool:
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (u,))
        return cursor.fetchone() is not None

    role_slug = (role or "staff").lower().replace(" ", "_")
    if login_id is not None:
        base = f"{role_slug}_{int(login_id)}"
        candidate = base
        suffix = 0
        while taken(candidate):
            suffix += 1
            candidate = f"{base}_{suffix}"
        conn.close()
        return candidate

    raw = (full_name or "").strip().lower()
    base_slug = re.sub(r"[^\w]+", "_", raw).strip("_")[:28]
    if not base_slug:
        base_slug = role_slug
    candidate = base_slug
    suffix = 0
    while taken(candidate):
        suffix += 1
        candidate = f"{base_slug}_{suffix}"
    conn.close()
    return candidate


def create_user(
    username: str,
    password: str,
    role: str,
    full_name: str = "",
    login_id: Optional[int] = None,
    email: str = "",
    phone: str = "",
    must_change_password: bool = False,
    created_by_user=None,
):
    salt = os.urandom(16)
    pw_hash = _hash_password(password, salt)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO users (
            username, full_name, role, login_id, email, phone,
            must_change_password, password_hash, salt, active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            username.strip(),
            full_name.strip() if full_name else None,
            role,
            login_id,
            (email or "").strip(),
            (phone or "").strip(),
            1 if must_change_password else 0,
            pw_hash,
            salt,
        ),
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
            details=f"Created user '{username}' role '{role}' login_id={login_id} email={(email or '').strip()[:48]}",
        )
    return uid


def _session_core_from_sql_row(row: tuple) -> Dict[str, Any]:
    """Map SELECT columns (no password fields) to session dict."""
    uid, uname, full_name, role, lid, doctor_id, email, phone, mcp = row
    return {
        "id": uid,
        "username": uname,
        "full_name": full_name or "",
        "role": role,
        "login_id": lid,
        "doctor_id": doctor_id,
        "email": email or "",
        "phone": phone or "",
        "must_change_password": bool(mcp),
    }


def get_user_session(user_id: int) -> Optional[Dict[str, Any]]:
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, full_name, role, login_id, doctor_id, email, phone, must_change_password
        FROM users WHERE id = ?
        """,
        (int(user_id),),
    )
    row = cursor.fetchone()
    conn.close()
    return _session_core_from_sql_row(row) if row else None


def get_users():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, full_name, role, login_id, active, created_at, email, phone, must_change_password
        FROM users ORDER BY created_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def authenticate(username: str, password: str):
    """Legacy username lookup — prefer authenticate_by_staff_id for interactive login."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, full_name, role, login_id, doctor_id, email, phone, must_change_password,
               password_hash, salt, active
        FROM users
        WHERE username = ?
        """,
        (username.strip(),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    uid, uname, full_name, role, login_id, doctor_id, email, phone, mcp, pw_hash, salt, active = row
    if not active:
        return None
    candidate = _hash_password(password, salt)
    if not hmac.compare_digest(pw_hash, candidate):
        return None
    base = _session_core_from_sql_row((uid, uname, full_name, role, login_id, doctor_id, email, phone, mcp))
    return base


def authenticate_by_staff_id(login_id: int, password: str):
    """All hospital staff sign in with unique numeric staff ID + password."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, full_name, role, login_id, doctor_id, email, phone, must_change_password,
               password_hash, salt, active
        FROM users
        WHERE login_id = ?
        """,
        (int(login_id),),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    uid, uname, full_name, role, lid, doctor_id, email, phone, mcp, pw_hash, salt, active = row
    if not active:
        return None
    candidate = _hash_password(password, salt)
    if not hmac.compare_digest(pw_hash, candidate):
        return None
    return _session_core_from_sql_row((uid, uname, full_name, role, lid, doctor_id, email, phone, mcp))


def authenticate_by_login_id(role: str, login_id: int, password: str):
    """Verify password for a staff ID when the portal role must match (same as staff login + role check)."""
    user = authenticate_by_staff_id(login_id, password)
    if not user or user.get("role") != role:
        return None
    return user

def set_user_login_id(user_id: int, login_id: Optional[int], doctor_id: Optional[int] = None):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET login_id = ?, doctor_id = ? WHERE id = ?", (login_id, doctor_id, user_id))
    conn.commit()
    conn.close()

def set_user_password(user_id: int, new_password: str, changed_by_user=None):
    salt = os.urandom(16)
    pw_hash = _hash_password(new_password, salt)
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ?, salt = ?, must_change_password = 0 WHERE id = ?",
        (pw_hash, salt, user_id),
    )
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


def delete_user(user_id: int, deleted_by_user=None):
    """Permanently remove a hospital staff user. Clears FK references; cannot delete Admin."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role, username, full_name, login_id FROM users WHERE id = ?",
        (int(user_id),),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("User not found.")
    _uid, role, uname, full_name, lid = row
    if role == "Admin":
        conn.close()
        raise ValueError("Administrator accounts cannot be deleted.")
    cursor.execute("UPDATE audit_log SET user_id = NULL WHERE user_id = ?", (int(user_id),))
    cursor.execute(
        "UPDATE password_reset_requests SET matched_user_id = NULL WHERE matched_user_id = ?",
        (int(user_id),),
    )
    cursor.execute(
        "UPDATE password_reset_requests SET resolved_by_user_id = NULL WHERE resolved_by_user_id = ?",
        (int(user_id),),
    )
    cursor.execute(
        "UPDATE inventory_movements SET user_id = NULL WHERE user_id = ?",
        (int(user_id),),
    )
    cursor.execute("DELETE FROM users WHERE id = ?", (int(user_id),))
    conn.commit()
    conn.close()
    if deleted_by_user:
        lid_disp = str(lid) if lid is not None else ""
        log_audit(
            user_id=deleted_by_user["id"],
            username=deleted_by_user["username"],
            action="DELETE_USER",
            entity_type="users",
            entity_id=int(user_id),
            details=f"Deleted '{uname}' role={role} login_id={lid_disp} name={(full_name or '')[:80]}",
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


def record_login_password_reset_request(login_id: int, notes: str = "") -> None:
    """Queue + audit a password reset request using staff login ID (any role)."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, role FROM users WHERE login_id = ?",
        (int(login_id),),
    )
    row = cursor.fetchone()
    uid = row[0] if row else None
    uname = row[1] if row else None
    role_str = row[2] if row else "Unknown"
    note_clean = (notes or "").strip() or None
    cursor.execute(
        """
        INSERT INTO password_reset_requests (role, login_id, notes, status, matched_user_id)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (role_str, int(login_id), note_clean, uid),
    )
    conn.commit()
    conn.close()
    parts = [f"role={role_str}", f"login_id={login_id}"]
    parts.append(f"matched_user={uname}" if uname else "matched_user=(none)")
    if note_clean:
        parts.append(f"note={note_clean}")
    log_audit(
        user_id=uid,
        username=uname or f"{role_str}:{login_id}",
        action="PASSWORD_RESET_REQUEST",
        entity_type="users",
        entity_id=uid,
        details="; ".join(parts),
    )


def list_pending_password_reset_requests():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, r.ts, r.role, r.login_id, COALESCE(r.notes, ''),
               r.matched_user_id, COALESCE(u.username, '')
        FROM password_reset_requests r
        LEFT JOIN users u ON u.id = r.matched_user_id
        WHERE r.status = 'pending'
        ORDER BY r.ts DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_password_reset_request_status(
    request_id: int, status: str, resolved_by_user_id: Optional[int] = None
) -> bool:
    if status not in ("completed", "dismissed"):
        raise ValueError("status must be 'completed' or 'dismissed'")
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE password_reset_requests
        SET status = ?, resolved_ts = CURRENT_TIMESTAMP, resolved_by_user_id = ?
        WHERE id = ? AND status = 'pending'
        """,
        (status, resolved_by_user_id, int(request_id)),
    )
    conn.commit()
    changed = cursor.rowcount > 0
    conn.close()
    return changed


def get_audit_logs(limit: int = 200):
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT ts, COALESCE(username,''), action, COALESCE(entity_type,''), COALESCE(entity_id,''), COALESCE(details,'')
        FROM audit_log
        ORDER BY ts DESC
        LIMIT ?
        """,
        (int(limit),),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_audit_logs_filtered(search: str = "", limit: int = 500):
    q = (search or "").strip()
    conn = connect()
    cursor = conn.cursor()
    if not q:
        cursor.execute(
            """
            SELECT ts, COALESCE(username,''), action, COALESCE(entity_type,''), COALESCE(entity_id,''), COALESCE(details,'')
            FROM audit_log
            ORDER BY ts DESC
            LIMIT ?
            """,
            (int(limit),),
        )
    else:
        like = f"%{q}%"
        cursor.execute(
            """
            SELECT ts, COALESCE(username,''), action, COALESCE(entity_type,''), COALESCE(entity_id,''), COALESCE(details,'')
            FROM audit_log
            WHERE username LIKE ? OR action LIKE ? OR entity_type LIKE ? OR CAST(entity_id AS TEXT) LIKE ? OR details LIKE ?
            ORDER BY ts DESC
            LIMIT ?
            """,
            (like, like, like, like, like, int(limit)),
        )
    rows = cursor.fetchall()
    conn.close()
    return rows

# ── PATIENT OPERATIONS ──

def add_patient(name, age, gender, contact, condition, hospital_card_number: Optional[str] = None):
    conn = connect()
    cursor = conn.cursor()
    card = (hospital_card_number or "").strip() or None
    if card:
        cursor.execute(
            "SELECT id FROM patients WHERE hospital_card_number = ? LIMIT 1",
            (card,),
        )
        if cursor.fetchone():
            conn.close()
            raise ValueError(f"Hospital card number '{card}' is already registered.")
    cursor.execute(
        """
        INSERT INTO patients (name, age, gender, contact, condition, hospital_card_number)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, age, gender, contact, condition, card),
    )
    conn.commit()
    patient_id = cursor.lastrowid
    conn.close()
    return patient_id


_PATIENT_SELECT = """
    SELECT id, name, age, gender, contact, condition, status, registered,
           hospital_card_number
    FROM patients
"""


def get_all_patients():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(_PATIENT_SELECT + " ORDER BY registered DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_active_patients():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(_PATIENT_SELECT + " WHERE status = 'Active' ORDER BY registered DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_patients(query):
    conn = connect()
    cursor = conn.cursor()
    q = f"%{(query or '').strip()}%"
    cursor.execute(
        _PATIENT_SELECT
        + """ WHERE name LIKE ? OR CAST(id AS TEXT) LIKE ?
               OR COALESCE(hospital_card_number,'') LIKE ?
        ORDER BY registered DESC
    """,
        (q, q, q),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def find_patient_by_hospital_card(card_number: str) -> Optional[int]:
    raw = (card_number or "").strip()
    if not raw:
        return None
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM patients WHERE hospital_card_number = ? LIMIT 1",
        (raw,),
    )
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else None


def resolve_patient_id_from_lookup(text: str) -> Optional[int]:
    """Resolve internal patient id from numeric ID or hospital card number."""
    t = (text or "").strip()
    if not t:
        return None
    if t.isdigit():
        pid = int(t)
        return pid if patient_exists(pid) else None
    return find_patient_by_hospital_card(t)

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
    cursor.execute(_PATIENT_SELECT + " WHERE id = ? LIMIT 1", (patient_id,))
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


def get_admin_kpis():
    """Aggregate metrics for Admin dashboard (no patient identifiers)."""
    s = get_stats()
    unpaid_count = 0
    outstanding = 0.0
    for inv in get_all_invoices():
        total = float(inv[4])
        paid = float(inv[5])
        bal = total - paid
        if bal > 1e-6:
            unpaid_count += 1
            outstanding += bal
    low_n = len(get_low_stock_items())
    pending_lab = 0
    for row in get_all_lab_orders():
        if row[4] in ("Ordered", "In Progress"):
            pending_lab += 1
    return {
        "patients_registered": s["total"],
        "appointments_today": s["today_appointments"],
        "registered_staff": count_registered_staff(True),
        "unpaid_invoice_count": unpaid_count,
        "outstanding_total": round(outstanding, 2),
        "low_stock_skus": low_n,
        "lab_orders_pending": pending_lab,
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


def get_active_doctors_for_booking():
    """Active doctors assigned to a department (required for reception booking workflow)."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.id, d.full_name, d.department_id, COALESCE(dep.name, '')
        FROM doctors d
        LEFT JOIN departments dep ON dep.id = d.department_id
        WHERE d.active = 1 AND d.department_id IS NOT NULL
        ORDER BY dep.name, d.full_name
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

def get_latest_encounter_id_for_patient(patient_id: int) -> Optional[int]:
    """Return latest encounter id for a patient (prefer Open, else latest any)."""
    conn = connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM encounters WHERE patient_id = ? AND status = 'Open' ORDER BY started_at DESC LIMIT 1",
        (patient_id,),
    )
    row = cursor.fetchone()
    if row:
        conn.close()
        return int(row[0])
    cursor.execute(
        "SELECT id FROM encounters WHERE patient_id = ? ORDER BY started_at DESC LIMIT 1",
        (patient_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return int(row[0]) if row else None

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
