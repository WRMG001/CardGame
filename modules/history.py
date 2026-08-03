# modules/history.py

import sqlite3
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "game.db")

def ensure_db_dir():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)

def get_db_connection():
    ensure_db_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_history_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            cards_drawn TEXT NOT NULL,
            combo_name TEXT NOT NULL,
            score_gained INTEGER NOT NULL,
            final_score INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def log_game_play(player_id, cards, combo_name, score_gained, final_score):
    try:
        init_history_table()
        conn = get_db_connection()
        cursor = conn.cursor()

        clean_player_id = str(player_id).strip().upper()
        cards_str = ", ".join(cards) if isinstance(cards, list) else str(cards)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO game_history (player_id, cards_drawn, combo_name, score_gained, final_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (clean_player_id, cards_str, combo_name, int(score_gained), int(final_score), now_str))

        conn.commit()
        conn.close()
        print(f"📜 บันทึกประวัติ {clean_player_id} เรียบร้อย | แต้มสุทธิ: {score_gained}")
    except Exception as e:
        print(f"❌ Error logging game play: {e}")

def get_player_history(player_id, limit=20):
    try:
        init_history_table()
        conn = get_db_connection()
        cursor = conn.cursor()

        clean_player_id = str(player_id).strip().upper()

        cursor.execute('''
            SELECT cards_drawn, combo_name, score_gained, final_score, created_at
            FROM game_history
            WHERE UPPER(TRIM(player_id)) = ?
            ORDER BY id DESC
            LIMIT ?
        ''', (clean_player_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [{
            "cards": row["cards_drawn"],
            "combo": row["combo_name"],
            "score_gained": row["score_gained"],
            "final_score": row["final_score"],
            "date": row["created_at"]
        } for row in rows]
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        return []
