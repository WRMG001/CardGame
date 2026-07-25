from datetime import datetime

# ตารางอธิบายประเภทบทบาทจาก Prefix
PREFIX_ROLES = {
    'C': 'Customer',
    'P': 'Partner',
    'H': 'Host',
    'BL': 'Black (Special Service)',
    'BA': 'Bartender',
    'W': 'Waiter',
    'G': 'Security Guard'
}

def parse_user_id(user_code):
    """ ตรวจสอบรหัสผู้เล่นและแยก Prefix เช่น C014 -> Prefix: C, ID: 014 """
    code = user_code.strip().upper()
    
    # เช็ก Prefix ที่ยาว 2 ตัวก่อน (เช่น BL, BA)
    for prefix in ['BL', 'BA']:
        if code.startswith(prefix) and code[len(prefix):].isdigit():
            return {
                "valid": True,
                "user_code": code,
                "prefix": prefix,
                "role": PREFIX_ROLES.get(prefix, 'Staff'),
                "number": code[len(prefix):]
            }
            
    # เช็ก Prefix 1 ตัว (C, P, H, W, G)
    for prefix in ['C', 'P', 'H', 'W', 'G']:
        if code.startswith(prefix) and code[len(prefix):].isdigit():
            return {
                "valid": True,
                "user_code": code,
                "prefix": prefix,
                "role": PREFIX_ROLES.get(prefix, 'User'),
                "number": code[len(prefix):]
            }
            
    return {"valid": False, "error": "รูปแบบรหัสไม่ถูกต้อง (เช่น C014, BA002)"}


def get_today_str():
    """ ดึงวันที่ปัจจุบัน YYYY-MM-DD """
    return datetime.now().strftime('%Y-%m-%d')


def init_user_session_data(user_info):
    """ สร้างข้อมูลเริ่มต้นของผู้เล่นเมื่อเข้าสู่ระบบ """
    today = get_today_str()
    return {
        "user_code": user_info["user_code"],
        "role": user_info["role"],
        "prefix": user_info["prefix"],
        "total_score": 0,
        "player_luck": 0,          # Lucky Protection (0 - 20%)
        "last_play_date": today,
        "free_plays_used": 0,      # ใช้สิทธิ์ฟรีไปแล้วกี่ครั้ง (Max 2)
        "bought_plays_used": 0     # ใช้สิทธิ์ซื้อไปแล้วกี่ครั้ง (Max 3)
    }


def check_and_reset_daily_limits(user_data):
    """ รีเซ็ตสิทธิ์ประจำวันถ้าข้ามวันแล้ว """
    today = get_today_str()
    if user_data.get("last_play_date") != today:
        user_data["last_play_date"] = today
        user_data["free_plays_used"] = 0
        user_data["bought_plays_used"] = 0
    return user_data