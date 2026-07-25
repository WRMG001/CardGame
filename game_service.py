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

def play_game(player_luck=0.0, event_luck=0.0, player_score=10):
    """
    ฟังก์ชันหลักในการเล่นเกม 1 รอบ (รับ player_score เข้ามาเพื่อเช็กค่า cost)
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

    # 3. ตรวจหา คอมโบ
    try:
        combo_name = check_combo(cards)
    except Exception as e:
        print(f"⚠️ Combo Check Error: {e}")
        combo_name = "High Card"

    # 4. คำนวณคะแนนตามคอมโบ (แก้ไขการส่งพารามิเตอร์ให้ถูกต้อง)
    try:
        raw_score, play_cost, final_score, can_play = calculate_score(combo_name, player_score)
    except Exception as e:
        print(f"⚠️ Score Calculate Error: {e}")
        # แก้ไข Fallback เป็น 0 เพื่อป้องกันคะแนนหลุด
        raw_score = 0
        play_cost = 0
        final_score = 0

    # 5. ปรับค่า Player Luck
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