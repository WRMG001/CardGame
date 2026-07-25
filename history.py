import sqlite3
import os
from datetime import datetime

# Path ไปยังไฟล์ database/game.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "game.db")

def init_history_table():
    """ สร้างตาราง game_history ถ้ายังไม่มี """
    conn = sqlite3.connect(DB_PATH)
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
    """ บันทึกประวัติการเล่น 1 รอบลง SQLite """
    try:
        init_history_table()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cards_str = ", ".join(cards) if isinstance(cards, list) else str(cards)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO game_history (player_id, cards_drawn, combo_name, score_gained, final_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (player_id, cards_str, combo_name, score_gained, final_score, now_str))

        conn.commit()
        conn.close()
        print(f"📜 บันทึกประวัติการเล่นของ {player_id} เรียบร้อย")
    except Exception as e:
        print(f"❌ Error logging game play: {e}")

def get_player_history(player_id, limit=20):
    """ ดึงประวัติการเล่นย้อนหลังของผู้เล่นรายคน """
    try:
        init_history_table()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT cards_drawn, combo_name, score_gained, final_score, created_at
            FROM game_history
            WHERE player_id = ?
            ORDER BY id DESC
            LIMIT ?
        ''', (player_id, limit))

        rows = cursor.fetchall()
        conn.close()

        history_list = []
        for row in rows:
            history_list.append({
                "cards": row["cards_drawn"],
                "combo": row["combo_name"],
                "score_gained": row["score_gained"],
                "final_score": row["final_score"],
                "date": row["created_at"]
            })
        return history_list
    except Exception as e:
        print(f"❌ Error fetching player history: {e}")
        return []