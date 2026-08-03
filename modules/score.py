# modules/score.py

# 🟢 รวมคะแนนคอมโบทั้งหมดไว้ที่เดียว
SCORES = {
    # คอมโบมาตรฐาน
    "High Card": 0,
    "One Pair": 3,
    "Two Pair": 5,
    "Three of a Kind": 15,
    "Straight": 10,
    "Flush": 5,
    "Full House": 20,
    "Four of a Kind": 30,
    "Straight Flush": 50,
    "Royal Straight Flush": 80,
    "Royal Combo": 60,
    "Joker Trio": 100,
    
    # คอมโบ Joker
    "Double Joker 🃏🃏": 10,
    "Wild Triple 🎰": 8,
    "Wild Pair 🃏✨": 5
}

PLAY_COST = 1

def calculate_score(combo_name, current_score=0):
    """
    คำนวณคะแนนดิบ ค่าธรรมเนียม คะแนนสุทธิ และคะแนนสะสมใหม่
    """
    raw_score = SCORES.get(combo_name, 0)
    score_gained = raw_score - PLAY_COST
    final_score = current_score + score_gained
    can_play = True

    return {
        "raw_score": raw_score,
        "play_cost": PLAY_COST,
        "score_gained": score_gained,
        "final_score": final_score,
        "can_play": can_play
    }
