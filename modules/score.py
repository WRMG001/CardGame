# modules/score.py

# 🟢 ตารางคะแนนดิบ (Raw Score) สำหรับสำรับ 55 ใบ (มี Joker 3 ใบ)
# ปรับแต่งตาม % ความยากทางสถิติ และความคุ้มค่าของผู้เล่น (Player Experience)
SCORES = {
    "Joker Trio": 100,             # 0.0038% (ยากที่สุดในเกม)
    "Royal Straight Flush": 80,    # 0.061%
    "Straight Flush": 60,          # 0.183%
    "Three of a Kind": 50,         # 0.198% (ตองปกติ)
    "Wild Triple 🎰": 30,           # 0.59% (Double Joker + ไพ่ธรรมดา)
    "Straight": 25,                # 2.74% (เรียง)
    "Flush": 20,                   # 4.17% (ดอกเดียวกัน)
    "Royal Combo": 15,             # 4.26% (ไพ่หน้าคน J, Q, K, A)
    "Wild Pair 🃏✨": 5,            # 15.16% (Joker 1 ใบ - ให้รางวัลความแรร์)
    "One Pair": 3,                 # 14.27% (คู่ธรรมดา)
    "High Card": 0                 # 58.38% (ไพ่ขยะ / ไม่เข้าคอมโบ)
}

PLAY_COST = 1

def calculate_score(combo_name, current_score=0):
    """
    คืนค่าคะแนนดิบ (Raw Score) สำหรับโชว์บน UI 
    และคะแนนสุทธิหลังหักค่าเล่นสำหรับอัปเดต DB/Sheets
    """
    # 1. แปลงค่า current_score ป้องกันการเกิด TypeError กรณีรับข้อมูลแบบ String เข้ามา
    try:
        current_score = int(current_score)
    except (ValueError, TypeError):
        current_score = 0

    # 2. ดึงคะแนนดิบตามชื่อคอมโบ (หากไม่เจอคอมโบ ให้ใช้ค่า default = 0)
    raw_score = SCORES.get(combo_name, 0)
    
    # 3. คำนวณแต้มประจำรอบ และแต้มสะสมใหม่
    score_gained = raw_score - PLAY_COST
    final_score = current_score + score_gained

    return {
        "combo_name": combo_name,               # ชื่อคอมโบ
        "raw_score": raw_score,                 # แต้มดิบ
        "play_cost": PLAY_COST,                 # ค่าธรรมเนียม (1)
        "score_gained": score_gained,           # แต้มสุทธิประจำรอบ (-1, +3, +7 ฯลฯ)
        "final_score": final_score,             # แต้มสะสมใหม่
        "is_win": raw_score > PLAY_COST,        # เช็กว่ารอบนี้กำไรหรือไม่ (ใช้ทำ Effect/Sound บน UI)
        "formatted_gained": f"+{score_gained}" if score_gained > 0 else str(score_gained) # ข้อความพร้อมเครื่องหมาย +/- เช่น "+19", "-1"
    }
