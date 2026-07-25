from datetime import datetime
from flask import session
from modules.sheets_service import get_player_data

def get_today_str():
    """ ดึงวันที่ปัจจุบัน YYYY-MM-DD """
    return datetime.now().strftime('%Y-%m-%d')

def login_player(player_id):
    player_id = player_id.strip().upper()
    
    # 1. ดึงข้อมูลจริงจาก Google Sheet
    player_info = get_player_data(player_id)
    
    # 2. ถ้าเจอข้อมูลใน Google Sheet
    if player_info:
        today = get_today_str()
        
        # 🔑 บันทึก sheet_name และ row_idx เพื่อใช้อัปเดตคะแนน
        session["sheet_name"] = player_info["sheet_name"]
        session["row_idx"] = player_info["row_idx"]
        
        session["player_id"] = player_info["player_id"]
        session["player_name"] = player_info["player_name"]
        session["role"] = player_info["role"]
        session["total_score"] = player_info["total_score"]
        session["player_luck"] = player_info["player_luck"]
        
        if player_info.get("last_play_date") != today:
            session["last_play_date"] = today
            session["free_plays_used"] = 0
            session["bought_plays_used"] = 0
        else:
            session["last_play_date"] = player_info.get("last_play_date")
            session["free_plays_used"] = player_info.get("free_plays_used", 0)
            session["bought_plays_used"] = player_info.get("bought_plays_used", 0)
            
        return True

    return False

def logout_player():
    session.clear()