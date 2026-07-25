def update_player_luck(current_luck, combo, cards=None):
    MAX_LUCK_CAP = 10.0  # จำกัดค่า Luck สูงสุดไว้ที่ 10%

    # เช็กว่ามีไพ่สูง (J, Q, K, A) หรือไม่
    has_high_card = False
    if cards:
        has_high_card = any(any(rank in card for rank in ['J', 'Q', 'K', 'A']) for card in cards)

    # เงื่อนไขการเพิ่ม Luck +1%
    if combo in ["High Card", "One Pair"] or has_high_card:
        new_luck = current_luck + 1.0
    else:
        # ถ้าได้ Combo ใหญ่ ให้ลด Luck กลับมา
        new_luck = current_luck - 2.0

    # คุมขอบเขต Luck อยู่ในช่วง 0.0% ถึง 10.0%
    return round(min(max(0.0, new_luck), MAX_LUCK_CAP), 2)