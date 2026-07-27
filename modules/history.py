import sqlite3
import os
from datetime import datetime

# Path ไปยังไฟล์ database/game.db
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "game.db")

def ensure_db_dir():
    """ ตรวจสอบและสร้างโฟลเดอร์ database ถ้ายังไม่มี """
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR, exist_ok=True)

def init_history_table():
    """ สร้างตาราง game_history ถ้ายังไม่มี """
    ensure_db_dir()
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

def log_game_play(player_id, cards, combo=None, combo_name=None, score_gained=0, final_score=0, total_score=0):
    """ 
    บันทึกประวัติการเล่น 1 รอบลง SQLite 
    รองรับ Parameter จาก app.py ทั้งแบบ combo, combo_name, final_score, total_score
    """
    try:
        init_history_table()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. จัดการคลีน Player ID
        clean_player_id = str(player_id).strip().upper()
        
        # 2. จัดการเรื่องไพ่
        cards_str = ", ".join(cards) if isinstance(cards, list) else str(cards)
        
        # 3. รองรับชื่อ Parameter ทั้ง combo และ combo_name
        actual_combo = combo if combo is not None else (combo_name or "ปกติ")
        
        # 4. รองรับแต้มรอบนี้และแต้มรวมสุทธิ (ถ้า app.py ส่ง final_score เป็นแต้มรอบนี้ และ total_score เป็นแต้มรวม)
        actual_score_gained = final_score if score_gained == 0 and final_score != 0 else score_gained
        actual_total_score = total_score if total_score != 0 else final_score

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO game_history (player_id, cards_drawn, combo_name, score_gained, final_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (clean_player_id, cards_str, actual_combo, actual_score_gained, actual_total_score, now_str))

        conn.commit()
        conn.close()
        print(f"📜 บันทึกประวัติการเล่นของ {clean_player_id} เรียบร้อย")
    except Exception as e:
        print(f"❌ Error logging game play: {e}")

def get_player_history(player_id, limit=20):
    """ ดึงประวัติการเล่นย้อนหลังของผู้เล่นรายคน """
    try:
        init_history_table()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
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
