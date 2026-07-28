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
    """
    คำนวณคะแนนสุทธิจากคอมโบไพ่
    - raw_score: แต้มดิบจากตาราง
    - play_cost: หักค่าเปิดไพ่ (0 แต้ม เพราะใช้ระบบตัดสิทธิ์สิทธิ์เล่นประจำวันแทน)
    """
    play_cost = 0
    raw_score = COMBO_SCORES.get(combo_name, 0)
    score_gained = raw_score - play_cost
    
    return raw_score, play_cost, score_gained, True
