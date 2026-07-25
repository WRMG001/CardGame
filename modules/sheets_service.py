import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_ID = "1szuc_r6rtGMRp2HWqbUNUFmlo-TgrsWY7LC_fZnLGq0"

PREFIX_ROLES = {
    'C': 'Customer',
    'P': 'Partner',
    'H': 'Host',
    'BL': 'Black (Special Service)',
    'BA': 'Bartender',
    'W': 'Waiter',
    'G': 'Security Guard'
}

def parse_role_from_prefix(player_id):
    """ ตรวจสอบ Prefix เพื่อเปลี่ยนเป็น Role """
    code = player_id.strip().upper()
    for prefix in ['BL', 'BA']:
        if code.startswith(prefix):
            return PREFIX_ROLES.get(prefix, 'Staff')
            
    for prefix in ['C', 'P', 'H', 'W', 'G']:
        if code.startswith(prefix):
            return PREFIX_ROLES.get(prefix, 'User')
            
    return 'User'


def get_client():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "credentials.json")
    
    try:
        creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"❌ Error initializing Google Sheets Client: {e}")
        return None


def safe_int(val, default=0):
    try:
        s = str(val).strip().replace(',', '')
        if s.lstrip('-').isdigit():
            return int(s)
    except:
        pass
    return default


def safe_float(val, default=0.0):
    try:
        s = str(val).strip().replace(',', '')
        return float(s)
    except:
        return default


def get_player_data(player_id):
    """ ค้นหารหัสผู้เล่นจากทุก ชีต ในไฟล์ """
    client = get_client()
    if not client:
        return None

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        search_id = player_id.strip().upper()
        
        for worksheet in spreadsheet.worksheets():
            all_rows = worksheet.get_all_values()
            
            for row_idx, row in enumerate(all_rows, start=1):
                if not row or len(row) < 2:
                    continue
                
                cell_code = str(row[1]).strip().upper()
                
                if cell_code == search_id:
                    code_id = str(row[1]).strip()
                    code_name = str(row[2]).strip() if len(row) > 2 and str(row[2]).strip() else code_id
                    role = parse_role_from_prefix(code_id)

                    total_score = safe_int(row[4]) if len(row) > 4 else 0
                    player_luck = safe_float(row[5]) if len(row) > 5 else 0.0
                    last_play_date = str(row[6]).strip() if len(row) > 6 else ""
                    free_plays_used = safe_int(row[7]) if len(row) > 7 else 0
                    bought_plays_used = safe_int(row[8]) if len(row) > 8 else 0

                    return {
                        "sheet_name": worksheet.title,
                        "row_idx": row_idx,
                        "player_id": code_id,
                        "player_name": code_name,
                        "role": role,
                        "total_score": total_score,
                        "player_luck": player_luck,
                        "last_play_date": last_play_date,
                        "free_plays_used": free_plays_used,
                        "bought_plays_used": bought_plays_used,
                    }
    except Exception as e:
        print(f"Error reading sheets: {e}")
        
    return None


def update_player_data(sheet_name, row_idx, score_to_add, new_luck, last_play_date, free_plays_used, bought_plays_used):
    """ อัปเดตข้อมูลกลับลง Google Sheet ตรงตามชื่อชีตและแถวของผู้เล่น """
    client = get_client()
    if not client:
        return False

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.worksheet(sheet_name)
        
        current_score_val = sheet.cell(row_idx, 5).value  
        current_score = safe_int(current_score_val)
        updated_score = current_score + score_to_add

        sheet.update_cell(row_idx, 5, updated_score)
        sheet.update_cell(row_idx, 6, round(new_luck, 2))
        sheet.update_cell(row_idx, 7, last_play_date)
        sheet.update_cell(row_idx, 8, free_plays_used)
        sheet.update_cell(row_idx, 9, bought_plays_used)

        print(f"✅ บันทึกสำเร็จ [{sheet_name} Row {row_idx}]: คะแนนรวม = {updated_score}")
        return True
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการอัปเดต Sheet: {e}")
        return False


def get_leaderboard(limit=100, period="all"):
    """ ดึงอันดับผู้เล่นจากทุกชีตแบบอ้างอิงตำแหน่งคอลัมน์จริง """
    client = get_client()
    if not client:
        print("❌ ไม่สามารถเชื่อมต่อ Google Sheets Client ได้")
        return []

    all_players = []

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        
        for worksheet in spreadsheet.worksheets():
            try:
                all_rows = worksheet.get_all_values()
                
                # ข้ามบรรทัด Header (วนลูปตั้งแต่อ่านแถวข้อมูลจริง)
                for row in all_rows:
                    if not row or len(row) < 5:
                        continue
                    
                    code_id = str(row[1]).strip()
                    # ถ้าช่อง Code ไม่ใช่รูปแบบ ID ผู้เล่น ให้ข้าม
                    if not code_id or code_id.upper() in ["CODE", "PLAYER_ID", "ID", "รหัส"]:
                        continue

                    code_name = str(row[2]).strip() if len(row) > 2 and str(row[2]).strip() else code_id
                    score = safe_int(row[4]) if len(row) > 4 else 0
                    role = parse_role_from_prefix(code_id)

                    if score > 0:
                        all_players.append({
                            "player_id": code_id,
                            "player_name": code_name,
                            "role": role,
                            "total_score": score
                        })
            except Exception as e:
                print(f"⚠️ Warning reading sheet {worksheet.title}: {e}")

        # จัดอันดับตามคะแนน total_score จากมากไปน้อย
        all_players.sort(key=lambda x: x["total_score"], reverse=True)
        return all_players[:limit]

    except Exception as e:
        print(f"❌ Error fetching leaderboard: {e}")
        return []