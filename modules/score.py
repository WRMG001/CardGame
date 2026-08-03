# ตัวอย่างโค้ดใน modules/score.py

def calculate_score(combo_name, current_score=0):
    # 1. กำหนดคะแนนดิบของแต่ละคอมโบ
    SCORES = {
        "High Card": 0,
        "One Pair": 3,         # ได้ 3 - ค่ากด 1 = สุทธิ +2
        "Two Pair": 5,         # ได้ 5 - ค่ากด 1 = สุทธิ +4
        "Three of a Kind": 8,
        "Straight": 10,
        "Flush": 15,
        "Full House": 20,
        "Four of a Kind": 30,
        "Straight Flush": 50,
        "Royal Flush": 100
    }
    
    # 🟢 2. กำหนดค่าธรรมเนียมการเล่น 1 แต้มเสมอ
    PLAY_COST = 1 
    
    # ดึงคะแนนคอมโบ (ถ้าไม่เจอให้เป็น 0)
    raw_score = SCORES.get(combo_name, 0)
    
    # 🟢 3. คำนวณคะแนนสุทธิที่จะได้รับ/หักในรอบนี้
    # High Card: 0 - 1 = -1 แต้ม
    # One Pair:  3 - 1 = +2 แต้ม
    score_gained = raw_score - PLAY_COST
    
    # คำนวณคะแนนรวมใหม่
    final_score = current_score + score_gained
    
    # สามารถเล่นได้ตลอดเวลา (แม้ติดลบ)
    can_play = True 

    # คืนค่า: raw_score, play_cost, final_score, can_play
    return score_gained, PLAY_COST, final_score, can_play
