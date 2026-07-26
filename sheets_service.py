import os
import json
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_client():
    creds_env = os.getenv('GOOGLE_CREDENTIALS')
    
    if creds_env:
        try:
            creds_dict = json.loads(creds_env)
            
            # จัดการ private_key ให้ถูกต้อง
            if 'private_key' in creds_dict:
                pk = creds_dict['private_key']
                # แปลงข้อความ \n ให้กลายเป็น escape character ขึ้นบรรทัดใหม่จริง
                pk = pk.replace('\\n', '\n')
                creds_dict['private_key'] = pk
                
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
