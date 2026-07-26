import os
import json
import gspread
from google.oauth2.service_account import Credentials

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
            if 'private_key' in creds_dict:
                creds_dict['private_key'] = clean_private_key(creds_dict['private_key'])
                
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
    if code.startswith('ADMIN'):
        return 'admin'
    elif code.startswith('STU'):
        return 'student'
    return 'player'

def get_player_data(player_id):
    """ ค้นหารหัสผู้เล่นจากทุกชีตในไฟล์ Google Sheet """
    client = get_client()
    if not client:
        print("❌ ไม่สามารถสร้าง gspread client ได้")
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
                    padded_row = row + [""] * (9 - len(row)) if len(row) < 9 else row
                    
                    code_id = str(padded_row[1]).strip()
                    code_name = str(padded_row[2]).strip() if str(padded_row[2]).strip() else code_id
                    role = parse_role_from_prefix(code_id)

                    return {
                        "sheet_name": worksheet.title,
                        "row_idx": row_idx,
                        "player_id": code_id,
                        "player_name": code_name,
                        "role": role,
                        "total_score": safe_int(padded_row[4]),
                        "player_luck": safe_float(padded_row[5]),
                        "last_play_date": str(padded_row[6]).strip(),
                        "free_plays_used": safe_int(padded_row[7]),
                        "bought_plays_used": safe_int(padded_row[8]),
                    }
    except Exception as e:
        print(f"❌ เกิด Error ขณะอ่าน Sheet: {e}")
        
    return None
