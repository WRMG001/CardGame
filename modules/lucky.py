def update_player_luck(current_luck, combo, cards=None):
    MAX_LUCK_CAP = 10.0  # จำกัดค่า Luck สูงสุดไว้ที่ 10.0

    try:
        current_luck = float(current_luck)
    except (ValueError, TypeError):
        current_luck = 0.0

    # 🎯 เงื่อนไขการปรับ Luck
    if combo == "High Card":
        # ถ้าเกลือ (ได้แค่ High Card) -> สะสม Luck เพิ่ม +1.0
        new_luck = current_luck + 1.0
    else:
        # ถ้าได้คอมโบใดๆ (One Pair, Wild Pair, Double Joker, Three of a Kind ฯลฯ)
        # ให้รีเซ็ต Luck กลับเป็น 0.0 ทันที!
        new_luck = 0.0

    # คุมขอบเขต Luck ให้อยู่ในช่วง 0.0 ถึง 10.0
    return round(min(max(0.0, new_luck), MAX_LUCK_CAP), 2)
