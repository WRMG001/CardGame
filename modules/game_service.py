import random
from modules.card_engine import draw_cards
from modules.combo import check_combo
from modules.score import calculate_score
from modules.lucky import update_player_luck

def format_card_to_string(card):
    if isinstance(card, dict):
        rank = card.get("rank", card.get("value", ""))
        suit = card.get("suit", "")
        return f"{rank}{suit}".strip()
    return str(card).strip()

def evaluate_joker_combo(cards):
    """
    ฟังก์ชันช่วยตรวจเช็กและคำนวณคอมโบพิเศษสำหรับ Joker
    """
    joker_cards = [c for c in cards if "Joker" in str(c)]
    joker_count = len(joker_cards)

    if joker_count == 0:
        return None  # ไม่มี Joker ให้กลับไปใช้ลอจิกคอมโบปกติ

    # 🃏1. กรณีได้ Joker 2 ใบ (สูงสุด)
    if joker_count >= 2:
        return {
            "combo": "Double Joker 🃏🃏",
            "raw_score": 10,
            "play_cost": 0,
            "final_score": 10
        }

    # 🃏2. กรณีได้ Joker 1 ใบ (Wild Card)
    # ให้ Joker แปลงร่างช่วยไพ่ปกติที่เหลืออีก 2 ใบ
    normal_cards = [c for c in cards if "Joker" not in str(c)]
    
    # ดึงเฉพาะ Value/Rank ของไพ่ปกติ เช่น 'Q♥' -> 'Q'
    ranks = [c[:-1] if len(c) > 1 and c[-1] in ['♠', '♥', '♦', '♣'] else c for c in normal_cards]

    # ถ้าไพ่ปกติอีก 2 ใบซ้ำกัน (เช่น Q, Q + Joker) -> ได้ Triple
    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return {
            "combo": "Wild Triple 🎰",
            "raw_score": 8,
            "play_cost": 0,
            "final_score": 8
        }
    
    # ถ้าไพ่ปกติไม่ซ้ำกัน (เช่น Q, A + Joker) -> Joker ช่วยจับคู่กับใบสูง ได้ Wild Pair
    return {
        "combo": "Wild Pair 🃏✨",
        "raw_score": 5,
        "play_cost": 0,
        "final_score": 5
    }

def play_game(player_luck=0.0, event_luck=0.0, player_score=10):
    """
    ฟังก์ชันหลักในการเล่นเกม 1 รอบ
    """
    # 1. คำนวณ Luck สุทธิ
    final_luck = round(player_luck + event_luck, 2)
    
    # 2. สุ่มไพ่ 3 ใบ
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

    # 3. เช็กคอมโบพิเศษสำหรับ Joker ก่อนเป็นอันดับแรก
    joker_result = evaluate_joker_combo(cards)

    if joker_result:
        combo_name = joker_result["combo"]
        raw_score = joker_result["raw_score"]
        play_cost = joker_result["play_cost"]
        final_score = joker_result["final_score"]
    else:
        # ถ้าไม่มี Joker ให้ส่งไปเช็กตามระบบปกติเดิม
        try:
            combo_name = check_combo(cards)
        except Exception as e:
            print(f"⚠️ Combo Check Error: {e}")
            combo_name = "High Card"

        try:
            raw_score, play_cost, final_score, can_play = calculate_score(combo_name, player_score)
        except Exception as e:
            print(f"⚠️ Score Calculate Error: {e}")
            raw_score = 0
            play_cost = 0
            final_score = 0

    # 4. ปรับค่า Player Luck
    try:
        next_luck = update_player_luck(current_luck=player_luck, combo=combo_name, cards=cards)
    except Exception as e:
        print(f"⚠️ Lucky Update Error: {e}")
        next_luck = player_luck

    return {
        "cards": cards,
        "combo": combo_name,
        "score": raw_score,
        "cost": play_cost,
        "final_score": final_score,
        "player_luck": player_luck,
        "event_luck": event_luck,
        "final_luck": final_luck,
        "next_player_luck": next_luck
    }
