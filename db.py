"""
db.py — Simple SQLite persistence layer for the KYC Document Verifier.

Creates/uses a local file `kyc_records.db` in the project folder.
No extra install needed — sqlite3 ships with Python.
"""

import os
import sqlite3
import hashlib
import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kyc_records.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            merchant_name TEXT NOT NULL,
            business_name TEXT,
            email TEXT NOT NULL,
            phone TEXT,
            age INTEGER,
            address TEXT,
            doc_type TEXT,
            detected_type TEXT,
            confidence TEXT,
            matches_expected INTEGER,
            flagged INTEGER,
            verdict TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            business_name TEXT,
            phone TEXT,
            age INTEGER,
            address TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


# ── Merchant accounts (Sign In / Register) ─────────────────────────────
# NOTE: password hashing here is a simple SHA-256 for demo purposes only.
# A real production system should use bcrypt/argon2 with a per-user salt.

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def register_merchant(name, email, password, age, address, business_name, phone):
    """Create a new merchant account. Returns (success: bool, error_message: str|None)."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO merchants (name, email, password_hash, business_name, phone, age, address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, email.strip().lower(), _hash_password(password),
            business_name, phone, age, address,
            datetime.datetime.now().isoformat(timespec="seconds"),
        ))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists. Please sign in instead."
    finally:
        conn.close()


def authenticate_merchant(email, password):
    """Returns the merchant record (dict) if email+password match, else None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM merchants WHERE email = ?", (email.strip().lower(),)
    ).fetchone()
    conn.close()
    if row and row["password_hash"] == _hash_password(password):
        return dict(row)
    return None


def find_latest_by_email(email: str):
    """Return the most recent record for this email, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM verifications WHERE email = ? ORDER BY created_at DESC LIMIT 1",
        (email.strip().lower(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def count_by_email(email: str) -> int:
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM verifications WHERE email = ?",
        (email.strip().lower(),),
    ).fetchone()
    conn.close()
    return row["c"] if row else 0


def insert_record(merchant_name, business_name, email, phone, age, address,
                   doc_type, detected_type, confidence, matches_expected,
                   flagged, verdict):
    conn = get_connection()
    conn.execute("""
        INSERT INTO verifications
            (merchant_name, business_name, email, phone, age, address,
             doc_type, detected_type, confidence, matches_expected, flagged,
             verdict, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        merchant_name, business_name, email.strip().lower(), phone, age, address,
        doc_type, detected_type, confidence, int(bool(matches_expected)),
        int(bool(flagged)), verdict,
        datetime.datetime.now().isoformat(timespec="seconds"),
    ))
    conn.commit()
    conn.close()


def get_recent_records(limit: int = 15):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM verifications ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]