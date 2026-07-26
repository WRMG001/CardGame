import os
import json
import base64
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
            # 1. ถอดรหัสจาก Base64 ก่อน
            try:
                decoded_bytes = base64.b64decode(creds_env)
                creds_dict = json.loads(decoded_bytes.decode('utf-8'))
            except Exception:
                # 2. ถ้ารับมาเป็น JSON ตรงๆ
                creds_dict = json.loads(creds_env)
            
            # จัดการ \n ใน private_key เผื่อกรณีไม่ได้ใช้ Base64
            if 'private_key' in creds_dict:
                creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
                
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
