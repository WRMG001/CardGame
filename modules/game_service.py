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

def evaluate_joker_combo(cards):
    joker_cards = [c for c in cards if "Joker" in str(c)]
    joker_count = len(joker_cards)

    if joker_count == 0:
        return None

    if joker_count >= 2:
        return {
            "combo": "Double Joker 🃏🃏",
            "raw_score": 10
        }

    normal_cards = [c for c in cards if "Joker" not in str(c)]
    ranks = [c[:-1] if len(c) > 1 and c[-1] in ['♠', '♥', '♦', '♣'] else c for c in normal_cards]

    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return {
            "combo": "Wild Triple 🎰",
            "raw_score": 8
        }
    
    return {
        "combo": "Wild Pair 🃏✨",
        "raw_score": 5
    }

def play_game(player_id=None, player_luck=0.0, event_luck=0.0, player_score=0):
    # 🟢 คำนวณ Luck รวม
    final_luck = round(player_luck + event_luck, 2)
    
    # 🟢 1. สุ่มไพ่
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

    # 🟢 2. ตรวจสอบคอมโบ (Joker หรือ ไพ่ปกติ)
    joker_result = evaluate_joker_combo(cards)

    if joker_result:
        combo_name = joker_result["combo"]
    else:
        try:
            combo_name = check_combo(cards)
        except Exception as e:
            print(f"⚠️ Combo Check Error: {e}")
            combo_name = "High Card"

    # 🟢 3. อัปเดต ค่า Luck ถัดไป
    try:
        next_luck = update_player_luck(current_luck=player_luck, combo=combo_name, cards=cards)
    except Exception as e:
        print(f"⚠️ Lucky Update Error: {e}")
        next_luck = player_luck

    # ส่งคืนแค่ข้อมูลไพ่ ชื่อคอมโบ และ Luck (ไม่คำนวณคะแนนในนี้)
    return {
        "success": True,
        "cards": cards,
        "combo": combo_name,
        "combo_name": combo_name,
        "player_luck": player_luck,
        "event_luck": event_luck,
        "final_luck": final_luck,
        "next_player_luck": next_luck
    }
