"""
persistence/session_store.py — SQLite-backed session persistence
"""

import sqlite3
import json
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "orchestrator.db")

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                patient_id TEXT,
                intent TEXT,
                response TEXT,
                source TEXT,
                escalated BOOLEAN,
                compliance_violation BOOLEAN,
                response_time_sec REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                session_id TEXT,
                agent TEXT,
                action TEXT,
                detail_json TEXT,
                timestamp TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                patient_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(session_id) REFERENCES sessions(session_id)
            )
        ''')
        conn.commit()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def save_session(result: dict, response_time_sec: float):
    with get_db_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO sessions (session_id, patient_id, intent, response, source, escalated, compliance_violation, response_time_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            result["session_id"],
            result["patient_id"],
            result["intent"],
            result.get("response", ""),
            result.get("source", ""),
            result["escalated"],
            result["compliance_violation"],
            response_time_sec
        ))
        # Save current turn to history
        if result.get("raw_query"):
            conn.execute('INSERT INTO messages (session_id, patient_id, role, content) VALUES (?, ?, ?, ?)',
                         (result["session_id"], result["patient_id"], "user", result["raw_query"]))
        
        if result.get("response"):
            conn.execute('INSERT INTO messages (session_id, patient_id, role, content) VALUES (?, ?, ?, ?)',
                         (result["session_id"], result["patient_id"], "assistant", result["response"]))

        # Restore audit log persistence
        for event in result.get("audit_log", []):
            skip_keys = {"event_id", "timestamp", "session_id", "agent", "action"}
            detail = {k: v for k, v in event.items() if k not in skip_keys}
            
            conn.execute('''
                INSERT OR IGNORE INTO audit_events (event_id, session_id, agent, action, detail_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                event["event_id"],
                event["session_id"],
                event["agent"],
                event["action"],
                json.dumps(detail),
                event["timestamp"]
            ))
        conn.commit()

def get_patient_memory(patient_id: str, limit: int = 10) -> dict:
    """Retrieves short-term history and generates long-term context from SQLite."""
    with get_db_connection() as conn:
        # Short-term: Last X messages
        history_rows = conn.execute('''
            SELECT role, content FROM messages 
            WHERE patient_id = ? 
            ORDER BY timestamp DESC LIMIT ?
        ''', (patient_id, limit)).fetchall()
        
        # Long-term: Summarized intents/issues
        summary_rows = conn.execute('''
            SELECT intent, COUNT(*) as count FROM sessions 
            WHERE patient_id = ? 
            GROUP BY intent
        ''', (patient_id,)).fetchall()
        
        history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
        
        lt_summary = []
        for row in summary_rows:
            lt_summary.append(f"{row['intent']} ({row['count']} times)")
        
        long_term = "Patient history summary: " + ", ".join(lt_summary) if lt_summary else "No prior history."
        
        return {
            "short_term": history,
            "long_term": long_term
        }

def get_session(session_id: str) -> dict:
    with get_db_connection() as conn:
        session_row = conn.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,)).fetchone()
        if not session_row:
            return None
            
        events_rows = conn.execute('SELECT * FROM audit_events WHERE session_id = ? ORDER BY timestamp ASC', (session_id,)).fetchall()
        
        audit_log = []
        for row in events_rows:
            event = {
                "event_id": row["event_id"],
                "session_id": row["session_id"],
                "agent": row["agent"],
                "action": row["action"],
                "timestamp": row["timestamp"]
            }
            if row["detail_json"]:
                event.update(json.loads(row["detail_json"]))
            audit_log.append(event)
            
        return dict(session_row) | {"audit_log": audit_log}

def list_sessions(limit: int = 50, offset: int = 0) -> list:
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return [dict(row) for row in rows]

# Initialize DB on load
init_db()
