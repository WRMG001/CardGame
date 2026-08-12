import random
import sqlite3
from modules.card_engine import draw_cards
from modules.combo import check_combo
from modules.score import calculate_score
from modules.lucky import update_player_luck

def get_db():
    conn = sqlite3.connect('database/game.db')
    conn.row_factory = sqlite3.Row
    
    try:
        conn.execute("ALTER TABLE players ADD COLUMN last_play_date TEXT;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    return conn

def format_card_to_string(card):
    if isinstance(card, dict):
        rank = card.get("rank", card.get("value", ""))
        suit = card.get("suit", "")
        return f"{rank}{suit}".strip()
    return str(card).strip()

def play_game(player_id=None, player_luck=0.0, event_luck=0.0, player_score=0):
    # 🟢 1. คำนวณ Luck รวม
    final_luck = round(player_luck + event_luck, 2)
    
    # 🟢 2. สุ่มไพ่ 3 ใบ
    try:
        raw_cards = draw_cards(luck=final_luck)
        if isinstance(raw_cards, list):
            cards = [format_card_to_string(c) for c in raw_cards]
        else:
            cards = [format_card_to_string(raw_cards)]
    except Exception as e:
        print(f"⚠️ Card Engine Error: {e}")
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        cards = [f"{random.choice(ranks)}{random.choice(suits)}" for _ in range(3)]

    # 🟢 3. ตรวจสอบคอมโบจาก combo.py (จัดการทั้ง Joker และไพ่ปกติอย่างถูกต้อง)
    try:
        combo_name = check_combo(cards)
    except Exception as e:
        print(f"⚠️ Combo Check Error: {e}")
        combo_name = "High Card"

    # 🟢 4. คำนวณคะแนนจาก score.py
    try:
        score_info = calculate_score(combo_name, current_score=player_score)
    except Exception as e:
        print(f"⚠️ Calculate Score Error: {e}")
        score_info = {
            "combo_name": combo_name,
            "raw_score": 0,
            "play_cost": 1,
            "score_gained": -1,
            "final_score": player_score - 1,
            "is_win": False,
            "formatted_gained": "-1"
        }

    # 🟢 5. อัปเดต ค่า Luck ถัดไป
    try:
        next_luck = update_player_luck(current_luck=player_luck, combo=combo_name, cards=cards)
    except Exception as e:
        print(f"⚠️ Lucky Update Error: {e}")
        next_luck = player_luck

    # 🟢 6. คืนค่าผลลัพธ์ทั้งหมดกลับไปที่ app.py หรือ Frontend
    return {
        "success": True,
        "cards": cards,
        "combo": combo_name,
        "combo_name": combo_name,
        "raw_score": score_info["raw_score"],
        "play_cost": score_info["play_cost"],
        "score_gained": score_info["score_gained"],
        "final_score": score_info["final_score"],
        "is_win": score_info["is_win"],
        "formatted_gained": score_info["formatted_gained"],
        "player_luck": player_luck,
        "event_luck": event_luck,
        "final_luck": final_luck,
        "next_player_luck": next_luck
    }

# -------------------------------------------------------------
# 🟢 ฟังก์ชันบันทึกประวัติการเล่น (แก้ไขเรื่อง Timezone UTC+7)
# -------------------------------------------------------------
def log_game_play(player_id, cards, combo=None, score_gained=0, final_score=0, **kwargs):
    """
    บันทึกประวัติลง SQLite ตาราง game_history 
    และอัปเดตคะแนนรวมล่าสุดลงตาราง players
    """
    combo_name = combo or kwargs.get("combo_name") or "High Card"

    try:
        conn = get_db()
        cursor = conn.cursor()

        # 1. สร้างตาราง game_history ถ้ายังไม่มี
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id TEXT,
                cards TEXT,
                combo TEXT,
                score_gained INTEGER,
                final_score INTEGER,
                created_at TEXT
            )
        """)

        # 2. บันทึกประวัติการเล่นรอบนี้ (ปรับเวลา UTC+7)
        cards_str = ", ".join(cards) if isinstance(cards, list) else str(cards)
        cursor.execute("""
            INSERT INTO game_history (player_id, cards, combo, score_gained, final_score, created_at)
            VALUES (?, ?, ?, ?, ?, DATETIME('now', '+7 hours'))
        """, (player_id, cards_str, combo_name, int(score_gained), int(final_score)))

        # 3. อัปเดตคะแนนรวมสะสมในตาราง players
        cursor.execute("""
            UPDATE players SET score = ? WHERE player_id = ?
        """, (int(final_score), player_id))

        conn.commit()
        conn.close()
        print(f"✅ Log saved successfully: {player_id} | Final Score: {final_score}")
    except Exception as e:
        print(f"❌ DB Log Error: {e}")


def get_player_history(player_id, limit=20):
    """
    ดึงประวัติการเล่นของผู้เล่นจาก SQLite
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cards, combo, score_gained, final_score, created_at 
            FROM game_history 
            WHERE player_id = ? 
            ORDER BY id DESC 
            LIMIT ?
        """, (player_id, limit))
        
        rows = cursor.fetchall()
        conn.close()

        history = []
        for r in rows:
            history.append({
                "cards": r["cards"],
                "combo": r["combo"],
                "score_gained": r["score_gained"],
                "final_score": r["final_score"],
                "created_at": r["created_at"]
            })
        return history
    except Exception as e:
        print(f"❌ Error fetching history: {e}")
        return []
