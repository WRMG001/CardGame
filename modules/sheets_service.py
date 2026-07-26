import os
import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def clean_private_key(key: str) -> str:
    """ จัดการเรื่อง \n ใน private_key ให้เป็น newline จริง ไม่ว่ามาในรูปแบบไหน """
    if not key:
        return key
    # ถ้ามี \n ที่เป็นข้อความหลุดมา ให้เปลี่ยนเป็นตัวขึ้นบรรทัดใหม่จริง
    cleaned = key.replace('\\n', '\n')
    # ป้องกันกรณีมี newline ซ้ำซ้อน
    return cleaned

def get_client():
    creds_env = os.getenv('GOOGLE_CREDENTIALS')
    
    if creds_env:
        try:
            creds_dict = json.loads(creds_env)
            
            # ทำความสะอาด private_key
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