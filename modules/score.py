COMBO_SCORES = {
    "Joker Trio": 100,
    "Royal Straight Flush": 80,
    "Royal Combo": 60,
    "Straight Flush": 50,
    "Three of a Kind": 15,
    "Straight": 8,
    "Flush": 5,
    "One Pair": 2,
    "High Card": 0
}

def calculate_score(combo_name, current_player_score=0):
    play_cost = 1  # ค่าเปิดไพ่รอบละ 1 แต้ม
    
    # เช็กว่าแต้มพอเล่นหรือไม่
    if current_player_score < play_cost:
        return 0, play_cost, 0, False  # แต้มไม่พอ
        
    raw_score = COMBO_SCORES.get(combo_name, 0)
    final_score = max(0, raw_score - play_cost)
    
    return raw_score, play_cost, final_score, True