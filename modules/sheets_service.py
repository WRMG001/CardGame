import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')

def clean_private_key(key: str) -> str:
    if not key:
        return key
    return key.replace('\\n', '\n')

def get_client():
    creds_env = os.getenv('GOOGLE_CREDENTIALS')
    
    if creds_env:
        try:
            creds_dict = json.loads(creds_env)
            # 🔧 แปลงตัวอักขระ \n ใน private_key ให้ถูกต้องสำหรับ Render
            if 'private_key' in creds_dict and creds_dict['private_key']:
                creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
                
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"❌ Error initializing credentials from ENV: {e}")
            return None
            
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "credentials.json")
    if os.path.exists(json_path):
        try:
            creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"❌ Error reading sheets from file: {e}")
            return None

    return None

def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def parse_role_from_prefix(code_id):
    code = code_id.strip().upper()
    
    # 1. Admin
    if code.startswith('ADMIN'):
        return 'admin'
        
    # 2. Partner & Customer (P, C)
    elif code.startswith('P') or code.startswith('C'):
        return 'customer'
        
    # 3. Host (H)
    elif code.startswith('H'):
        return 'host'
        
    # 4. Black (BL)
    elif code.startswith('BL'):
        return 'black'
        
    # 5. Bartender (BA)
    elif code.startswith('BA'):
        return 'bartender'
        
    # 6. Waiter (W)
    elif code.startswith('W'):
        return 'waiter'
        
    # 7. Security guard (G)
    elif code.startswith('G'):
        return 'security'
        
    # Default กรณีหลุดเงื่อนไข
    return 'customer'

# 1. ฟังก์ชันค้นหาข้อมูลผู้เล่น (พร้อม Auto-Reset สิทธิ์ถ้าข้ามวัน)
def get_player_data(player_id):
    client = get_client()
    if not client:
        print("❌ ไม่สามารถสร้าง gspread client ได้")
        return None

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        search_id = player_id.strip().upper()
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for worksheet in spreadsheet.worksheets():
            # ข้าม Sheet History ไม่ต้องค้นหาผู้เล่นในนี้
            if worksheet.title == "History":
                continue

            all_rows = worksheet.get_all_values()
            
            for row_idx, row in enumerate(all_rows, start=1):
                if not row or len(row) < 2:
                    continue
                
                cell_code = str(row[1]).strip().upper()
                
                if cell_code == search_id:
                    padded_row = row + [""] * (9 - len(row)) if len(row) < 9 else row
                    
                    code_id = str(padded_row[1]).strip()
                    code_name = str(padded_row[2]).strip() if str(padded_row[2]).strip() else code_id
                    role = parse_role_from_prefix(code_id)

                    last_play_date = str(padded_row[6]).strip()
                    free_plays_used = safe_int(padded_row[7])
                    bought_plays_used = safe_int(padded_row[8])

                    # 🔄 CHECK AUTO-RESET: ถ้าเป็นวันใหม่ ให้รีเซ็ตจำนวนที่ใช้ไปเป็น 0
                    if last_play_date != today_str:
                        free_plays_used = 0
                        bought_plays_used = 0

                    return {
                        "sheet_name": worksheet.title,
                        "row_idx": row_idx,
                        "player_id": code_id,
                        "player_name": code_name,
                        "role": role,
                        "total_score": safe_int(padded_row[4]),
                        "player_luck": safe_float(padded_row[5]),
                        "last_play_date": last_play_date,
                        "free_plays_used": free_plays_used,
                        "bought_plays_used": bought_plays_used,
                    }
    except Exception as e:
        print(f"❌ เกิด Error ขณะอ่าน Sheet: {e}")
        
    return None

# 2. ฟังก์ชันอัปเดตข้อมูลผู้เล่น
def update_player_data(sheet_name, row_idx, updated_data):
    client = get_client()
    if not client:
        return False
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # อัปเดต Column E ถึง I (คะแนน, ดวง, วันที่เล่นล่าสุด, จำนวนสิทธิ์ฟรี, สิทธิ์ซื้อ)
        cell_range = f"E{row_idx}:I{row_idx}"
        values = [[
            updated_data.get('total_score', 0),
            updated_data.get('player_luck', 0.0),
            updated_data.get('last_play_date', ''),
            updated_data.get('free_plays_used', 0),
            updated_data.get('bought_plays_used', 0)
        ]]
        worksheet.update(cell_range, values)
        return True
    except Exception as e:
        print(f"❌ เกิด Error ขณะอัปเดต Sheet: {e}")
        return False

# 3. ฟังก์ชันดึงตารางคะแนนสูงสุด (Leaderboard)
def get_leaderboard(limit=10):
    client = get_client()
    if not client:
        return []
        
    leaderboard = []
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        for worksheet in spreadsheet.worksheets():
            if worksheet.title == "History":
                continue
            all_rows = worksheet.get_all_values()
            for row in all_rows[1:]: # ข้ามหัวตาราง
                if len(row) >= 5:
                    p_id = str(row[1]).strip()
                    p_name = str(row[2]).strip() if len(row) > 2 and str(row[2]).strip() else p_id
                    score = safe_int(row[4])
                    if p_id:
                        leaderboard.append({
                            "player_id": p_id,
                            "player_name": p_name,
                            "total_score": score
                        })
                        
        # เรียงลำดับจากคะแนนมากไปน้อย
        leaderboard.sort(key=lambda x: x['total_score'], reverse=True)
        return leaderboard[:limit]
    except Exception as e:
        print(f"❌ เกิด Error ขณะดึง Leaderboard: {e}")
        return []

# 4. ฟังก์ชันดึงข้อมูลผู้เล่นทั้งหมด
def get_all_players():
    """ดึงข้อมูลผู้เล่นทั้งหมดจากทุก Sheet เพื่อนำมาแสดงในตาราง All Players"""
    client = get_client()
    if not client:
        return []

    all_players = []
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        for worksheet in spreadsheet.worksheets():
            if worksheet.title == "History":
                continue
            all_rows = worksheet.get_all_values()
            if not all_rows or len(all_rows) < 2:
                continue

            # วนลูปอ่านข้อมูลบรรทัดถัดจากหัวตาราง (Row 2 เป็นต้นไป)
            for row in all_rows[1:]:
                if not row or len(row) < 2:
                    continue

                player_id = str(row[1]).strip()
                if player_id:
                    padded_row = row + [""] * (8 - len(row)) if len(row) < 8 else row
                    name = str(padded_row[2]).strip() if str(padded_row[2]).strip() else player_id
                    score = safe_int(padded_row[4])
                    plays_used = safe_int(padded_row[7])

                    all_players.append({
                        'player_id': player_id,
                        'name': name,
                        'total_score': score,
                        'free_plays_used': plays_used,
                        'sheet_name': worksheet.title
                    })
    except Exception as e:
        print(f"❌ เกิด Error ขณะดึงข้อมูล All Players: {e}")

    return all_players

# 5. ฟังก์ชันบันทึกประวัติการเล่นลง Google Sheet "History"
def save_game_history(player_id, cards, combo, score_gained, final_score):
    client = get_client()
    if not client:
        return False
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = spreadsheet.worksheet("History")
        except Exception:
            worksheet = spreadsheet.add_worksheet(title="History", rows="1000", cols="6")
            worksheet.append_row(["Date", "Player ID", "Cards", "Combo", "Score Gained", "Final Score"])

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cards_str = ", ".join(cards) if isinstance(cards, list) else str(cards)
        clean_id = str(player_id).strip().upper()

        worksheet.append_row([
            now_str,
            clean_id,
            cards_str,
            str(combo),
            safe_int(score_gained),
            safe_int(final_score)
        ])
        print(f"📜 เซฟประวัติลง Sheet History สำเร็จ: {clean_id}")
        return True
    except Exception as e:
        print(f"❌ เกิด Error ขณะบันทึก History ลง Sheets: {e}")
        return False

# 6. ฟังก์ชันดึงประวัติการเล่นย้อนหลังจาก Google Sheet "History"
def get_history_from_sheets(player_id=None, limit=500):
    client = get_client()
    if not client:
        return []
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = spreadsheet.worksheet("History")
        except Exception:
            return []

        all_rows = worksheet.get_all_values()
        if not all_rows or len(all_rows) < 2:
            return []

        search_id = str(player_id).strip().upper() if player_id else None
        history_list = []

        # วนลูปอ่านย้อนหลังจากล่างขึ้นบน (ล่าสุดไปเก่าสุด)
        for row in reversed(all_rows[1:]):
            if len(row) >= 6:
                row_p_id = str(row[1]).strip().upper()
                
                # ถ้าใส่ player_id ให้เช็ค ID ตรงกัน / ถ้าไม่ใส่ player_id (None) ให้เอามาทั้งหมด
                if search_id is None or row_p_id == search_id:
                    history_list.append({
                        "date": str(row[0]),
                        "player_id": row_p_id,
                        "cards": str(row[2]),
                        "combo": str(row[3]),
                        "score_gained": safe_int(row[4]),
                        "final_score": safe_int(row[5])
                    })
                    if len(history_list) >= limit:
                        break

        return history_list
    except Exception as e:
        print(f"❌ เกิด Error ขณะดึง History จาก Sheets: {e}")
        return []กิด Error ขณะดึง History จาก Sheets: {e}")
        return []
