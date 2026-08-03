# modules/score.py

# 🟢 ตารางคะแนนดิบ (Raw Score) ของแต่ละคอมโบ
SCORES = {
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
    "Double Joker 🃏🃏": 10,
    "Wild Triple 🎰": 8,
    "Wild Pair 🃏✨": 5
}

PLAY_COST = 1

def calculate_score(combo_name, current_score=0):
    """
    คืนค่าคะแนนดิบ (Raw Score) สำหรับโชว์บน UI 
    และคะแนนสุทธิหลังหักค่าเล่นสำหรับอัปเดต DB/Sheets
    """
    raw_score = SCORES.get(combo_name, 0)
    score_gained = raw_score - PLAY_COST
    final_score = current_score + score_gained

    return {
        "raw_score": raw_score,          # แต้มดิบ (0, 3, 5, 10 ฯลฯ)
        "play_cost": PLAY_COST,          # ค่าธรรมเนียม (1)
        "score_gained": score_gained,    # แต้มสุทธิประจำรอบ (-1, +2, +4 ฯลฯ)
        "final_score": final_score       # แต้มสะสมใหม่
    }
