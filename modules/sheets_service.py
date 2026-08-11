import os
import json
import time
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')

# =============================================================
# ⚡ IN-MEMORY CACHE SYSTEM (ป้องกัน API 429 Quota Exceeded)
# =============================================================
_CACHE_EXPIRATION_SECONDS = 60  # ระยะเวลาเก็บ Cache (60 วินาที)

_PLAYERS_CACHE = None
_PLAYERS_CACHE_TIME = 0

_HISTORY_CACHE = None
_HISTORY_CACHE_TIME = 0

def clear_cache():
    """เคลียร์ Cache เมื่อมีการเขียนข้อมูลใหม่ (เช่น หลังบันทึก/อัปเดต)"""
    global _PLAYERS_CACHE, _HISTORY_CACHE
    _PLAYERS_CACHE = None
    _HISTORY_CACHE = None

# =============================================================
# 🔑 UTILITY & AUTHENTICATION
# =============================================================
def get_now_th():
    """ดึงเวลาปัจจุบันใน Timezone ประเทศไทย (UTC+7)"""
    tz_th = timezone(timedelta(hours=7))
    return datetime.now(tz_th)

def clean_private_key(key: str) -> str:
    if not key:
        return key
    return key.replace('\\n', '\n')

def get_client():
    creds_env = os.getenv('GOOGLE_CREDENTIALS')
    
    if creds_env:
        try:
            creds_dict = json.loads(creds_env)
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
    
    if code.startswith('ADMIN'):
        return 'admin'
    elif code.startswith('P') or code.startswith('C'):
        return 'customer'
    elif code.startswith('H'):
        return 'host'
    elif code.startswith('BL'):
        return 'black'
    elif code.startswith('BA'):
        return 'bartender'
    elif code.startswith('W'):
        return 'waiter'
    elif code.startswith('G'):
        return 'security'
        
    return 'customer'

# =============================================================
# 📊 CORE FUNCTIONS WITH CACHING
# =============================================================

# 1. ฟังก์ชันค้นหาข้อมูลผู้เล่น (พร้อม Auto-Reset สิทธิ์ถ้าข้ามวัน)
def get_player_data(player_id):
    search_id = player_id.strip().upper()
    
    # พยายามดึงข้อมูลจาก All Players เพื่อประหยัด API Rate Limit
    all_players = get_all_players()
    today_str = get_now_th().strftime("%Y-%m-%d")  # 🇹🇭 ปรับเป็นเวลาไทย UTC+7

    # ถ้ามีใน Cache อยู่แล้ว
    for player in all_players:
        if player.get("player_id", "").strip().upper() == search_id:
            break

    # ดึงตรงจาก Sheets หากต้องการตำแหน่ง row_idx เพื่อใช้อัปเดต
    client = get_client()
    if not client:
        print("❌ ไม่สามารถสร้าง gspread client ได้")
        return None

    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        
        for worksheet in spreadsheet.worksheets():
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

                    # 🇹🇭 Auto-Reset หากวันที่ใน Sheet ไม่ตรงกับเวลาไทยวันนี้
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
        
        cell_range = f"E{row_idx}:I{row_idx}"
        values = [[
            updated_data.get('total_score', 0),
            updated_data.get('player_luck', 0.0),
            updated_data.get('last_play_date', ''),
            updated_data.get('free_plays_used', 0),
            updated_data.get('bought_plays_used', 0)
        ]]
        worksheet.update(cell_range, values)
        
        # 🔄 เคลียร์ Cache เพื่อให้ครั้งถัดไปดึงข้อมูลที่อัปเดตแล้ว
        clear_cache()
        return True
    except Exception as e:
        print(f"❌ เกิด Error ขณะอัปเดต Sheet: {e}")
        return False

# 3. ฟังก์ชันดึงตารางคะแนนสูงสุด (Leaderboard)
def get_leaderboard(limit=10):
    all_players = get_all_players()
    if not all_players:
        return []
        
    sorted_players = sorted(all_players, key=lambda x: x.get('total_score', 0), reverse=True)
    
    leaderboard = []
    for p in sorted_players[:limit]:
        leaderboard.append({
            "player_id": p.get("player_id"),
            "player_name": p.get("name") or p.get("code_name") or p.get("player_id"),
            "total_score": p.get("total_score", 0)
        })
    return leaderboard

# 4. ฟังก์ชันดึงข้อมูลผู้เล่นทั้งหมด (มี Cache 60 วินาที)
def get_all_players():
    global _PLAYERS_CACHE, _PLAYERS_CACHE_TIME
    now = time.time()

    # คืนค่าจาก Cache หากยังไม่หมดอายุ
    if _PLAYERS_CACHE is not None and (now - _PLAYERS_CACHE_TIME) < _CACHE_EXPIRATION_SECONDS:
        return _PLAYERS_CACHE

    client = get_client()
    if not client:
        return _PLAYERS_CACHE or []

    all_players = []
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        for worksheet in spreadsheet.worksheets():
            if worksheet.title == "History":
                continue
            all_rows = worksheet.get_all_values()
            if not all_rows or len(all_rows) < 2:
                continue

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
                        'code_name': name,
                        'name': name,
                        'total_score': score,
                        'free_plays_used': plays_used,
                        'sheet_name': worksheet.title
                    })

        # บันทึกลง Cache
        _PLAYERS_CACHE = all_players
        _PLAYERS_CACHE_TIME = now
    except Exception as e:
        print(f"❌ เกิด Error ขณะดึงข้อมูล All Players: {e}")
        return _PLAYERS_CACHE or []

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

        now_str = get_now_th().strftime("%Y-%m-%d %H:%M:%S")  # 🇹🇭 บันทึกเวลาประวัติเป็นเวลาไทย
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
        
        # 🔄 เคลียร์ Cache History
        clear_cache()
        return True
    except Exception as e:
        print(f"❌ เกิด Error ขณะบันทึก History ลง Sheets: {e}")
        return False

# 6. ฟังก์ชันดึงประวัติการเล่นย้อนหลัง (มี Cache 60 วินาที)
def get_history_from_sheets(player_id=None, limit=500):
    global _HISTORY_CACHE, _HISTORY_CACHE_TIME
    now = time.time()

    search_id = str(player_id).strip().upper() if player_id else None

    # ดึงข้อมูลจาก Cache ถ้า Cache ยังใช้ได้
    if _HISTORY_CACHE is not None and (now - _HISTORY_CACHE_TIME) < _CACHE_EXPIRATION_SECONDS:
        raw_history = _HISTORY_CACHE
    else:
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

            raw_history = []
            for row in reversed(all_rows[1:]):
                if len(row) >= 6:
                    raw_history.append({
                        "date": str(row[0]),
                        "player_id": str(row[1]).strip().upper(),
                        "cards": str(row[2]),
                        "combo": str(row[3]),
                        "score_gained": safe_int(row[4]),
                        "final_score": safe_int(row[5])
                    })

            # อัปเดต Cache
            _HISTORY_CACHE = raw_history
            _HISTORY_CACHE_TIME = now
        except Exception as e:
            print(f"❌ เกิด Error ขณะดึง History จาก Sheets: {e}")
            return []

    # กรองข้อมูลตาม player_id (ถ้ามีระบุ)
    if search_id:
        filtered = [h for h in raw_history if h["player_id"] == search_id]
        return filtered[:limit]

    return raw_history[:limit]
