import os
import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

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
            print(f"Error reading sheets: {e}")
            return None
            
    # สำรองกรณีรันบน Local
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "credentials.json")
    if os.path.exists(json_path):
        try:
            creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"Error reading sheets from file: {e}")
            return None

    return None

# ==========================================
# ฟังก์ชันดึงข้อมูลที่ modules/auth.py เรียกใช้
# ==========================================

def get_player_data():
    client = get_client()
    if not client:
        print("Failed to initialize Google Sheets client.")
        return []
    
    try:
        # ใส่ชื่อ Google Sheet ของคุณตรงนี้ (หรือใช้ SPREADSHEET_ID จาก env)
        spreadsheet_name = os.getenv('SPREADSHEET_NAME', 'cardgame-sheet') 
        sheet = client.open(spreadsheet_name).sheet1
        return sheet.get_all_records()
    except Exception as e:
        print(f"Error fetching player data: {e}")
        return []
