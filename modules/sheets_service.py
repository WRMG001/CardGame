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
# ⚡ IN-MEMORY CACHE SYSTEM
# =============================================================
_CACHE_EXPIRATION_SECONDS = 30  # ปรับลดลงเหลือ 30 วินาที เพื่อให้หน้าเว็บดึงข้อมูลใหม่ได้ไวขึ้น

_PLAYERS_CACHE = None
_PLAYERS_CACHE_TIME = 0

_HISTORY_CACHE = None
_HISTORY_CACHE_TIME = 0

def clear_cache():
    """เคลียร์ Cache ทั้งหมดทันทีที่มีการเขียน/บันทึกข้อมูลใหม่"""
    global _PLAYERS_CACHE, _HISTORY_CACHE, _PLAYERS_CACHE_TIME, _HISTORY_CACHE_TIME
    _PLAYERS_CACHE = None
    _PLAYERS_CACHE_TIME = 0
    _HISTORY_CACHE = None
    _HISTORY_CACHE_TIME = 0

# =============================================================
# 🔑 UTILITY & AUTHENTICATION
# =============================================================
def get_now_th():
    """ดึงเวลาปัจจุบันใน Timezone ประเทศไทย (UTC+7) แบบการันตีความถูกต้อง"""
    tz_th = timezone(timedelta(hours=7))
    return datetime.now(timezone.utc).astimezone(tz_th)

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
                creds_dict['private_key'] = clean_private_key(creds_dict['private_key'])
                
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"❌ Error initializing credentials from ENV: {e}")
            
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "credentials.json")
    if os.path.exists(json_path):
        try:
            creds = Credentials.from_service_account_file(json_path, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print(f"❌ Error reading sheets from file: {e}")

    return None

def safe_int(val, default=0):
    try:
        if val is None or str(val).strip() == '':
            return default
        return int(float(val))
    except (ValueError, TypeError):
        return default

def safe_float(val, default=0.0):
    try:
        if val is None or str(val).strip() == '':
            return default
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
    elif code.startswith('OWNER'):
        return 'owner'
        
    return 'customer'

# =============================================================
# 📊 CORE FUNCTIONS
# =============================================================

def get_all_players():
    global _PLAYERS_CACHE, _PLAYERS_CACHE_TIME
    now = time.time()

    if _PLAYERS_CACHE is not None and (now - _PLAYERS_CACHE_TIME) < _CACHE_EXPIRATION_SECONDS:
        return _PLAYERS_CACHE

    client = get_client()
    if not client:
        return _PLAYERS_CACHE or []

    all_players = []
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        today_str = get_now_th().strftime("%Y-%m-%d")

        for worksheet in spreadsheet.worksheets():
            if worksheet.title in ["History", "Logs"]:
                continue
            all_rows = worksheet.get_all_values()
            if not all_rows or len(all_rows) < 2:
                continue

            for row_idx, row in enumerate(all_rows[1:], start=2):
                if not row or len(row) < 2:
                    continue

                player_id = str(row[1]).strip().upper()
                if player_id:
                    padded_row = row + [""] * (10 - len(row)) if len(row) < 10 else row
                    name = str(padded_row[2]).strip() if str(padded_row[2]).strip() else player_id
                    score = safe_int(padded_row[4])
                    luck = safe_float(padded_row[5])
                    last_play_date = str(padded_row[6]).strip()
                    free_plays_used = safe_int(padded_row[7])
                    bought_plays_used = safe_int(padded_row[8])

                    # Auto Reset วันใหม่
                    if last_play_date and last_play_date != today_str:
                        free_plays_used = 0
                        bought_plays_used = 0

                    all_players.append({
                        'sheet_name': worksheet.title,
                        'row_idx': row_idx,
                        'player_id': player_id,
                        'code_name': name,
                        'player_name': name,
                        'role': parse_role_from_prefix(player_id),
                        'total_score': score,
                        'player_luck': luck,
                        'last_play_date': last_play_date,
                        'free_plays_used': free_plays_used,
                        'bought_plays_used': bought_plays_used
                    })

        _PLAYERS_CACHE = all_players
        _PLAYERS_CACHE_TIME = now
    except Exception as e:
        print(f"❌ เกิด Error ขณะดึงข้อมูล All Players: {e}")
        return _PLAYERS_CACHE or []

    return all_players

def get_player_data(player_id):
    search_id = str(player_id).strip().upper()
    all_players = get_all_players()

    for player in all_players:
        if player.get("player_id", "").strip().upper() == search_id:
            return player.copy()

    return None

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
            updated_data.get('last_play_date', get_now_th().strftime("%Y-%m-%d")),
            updated_data.get('free_plays_used', 0),
            updated_data.get('bought_plays_used', 0)
        ]]
        worksheet.update(cell_range, values)
        
        # 🔄 เคลียร์ Cache ทันทีหลังอัปเดต
        clear_cache()
        return True
    except Exception as e:
        print(f"❌ เกิด Error ขณะอัปเดต Sheet: {e}")
        return False

def get_leaderboard(limit=10):
    all_players = get_all_players()
    if not all_players:
        return []
    
    # กรองเอา Admin ออกจาก Leaderboard
    valid_players = [p for p in all_players if not p.get('player_id', '').startswith('ADMIN')]
    sorted_players = sorted(valid_players, key=lambda x: x.get('total_score', 0), reverse=True)
    
    leaderboard = []
    for p in sorted_players[:limit]:
        leaderboard.append({
            "player_id": p.get("player_id"),
            "player_name": p.get("player_name") or p.get("player_id"),
            "total_score": p.get("total_score", 0)
        })
    return leaderboard

# 5. บันทึกประวัติการเล่นลง Sheet "History"
def save_game_history(player_id, cards, combo, score_gained, final_score):
    clean_id = str(player_id).strip().upper()
    
    # 🚫 ถ้าเป็น ADMIN ไม่ต้องบันทึกประวัติลง Google Sheet
    if clean_id.startswith("ADMIN"):
        print(f"🧪 [ADMIN TEST] ไม่บันทึก History ของ {clean_id} ลง Sheet")
        return True

    client = get_client()
    if not client:
        return False
    try:
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        try:
            worksheet = spreadsheet.worksheet("History")
        except Exception:
            worksheet = spreadsheet.add_worksheet(title="History", rows="1000", cols="6")
            worksheet.append_row(["Date", "Player ID", "Cards", "Combo", "Score Gained", " Final Score"])

        # บันทึกเวลาไทย GMT+7 เสมอ
        now_str = get_now_th().strftime("%Y-%m-%d %H:%M:%S")
        cards_str = ", ".join(cards) if isinstance(cards, list) else str(cards)

        worksheet.append_row([
            now_str,
            clean_id,
            cards_str,
            str(combo),
            safe_int(score_gained),
            safe_int(final_score)
        ])
        print(f"📜 เซฟประวัติลง Sheet History สำเร็จ: {clean_id} | {now_str} | Score: {final_score}")
        
        # 🔄 เคลียร์ Cache ทันที เพื่อให้ดึงประวัติล่าสุดมาโชว์ได้ทันที
        clear_cache()
        return True
    except Exception as e:
        print(f"❌ เกิด Error ขณะบันทึก History ลง Sheets: {e}")
        return False

# 6. ดึงประวัติการเล่นย้อนหลัง
def get_history_from_sheets(player_id=None, limit=100):
    global _HISTORY_CACHE, _HISTORY_CACHE_TIME
    now = time.time()

    search_id = str(player_id).strip().upper() if player_id else None

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
            # วนอ่านจากล่างขึ้นบน (ล่าสุดมาแรกสุด)
            for row in reversed(all_rows[1:]):
                if len(row) >= 6:
                    raw_history.append({
                        "date": str(row[0]).strip(),
                        "player_id": str(row[1]).strip().upper(),
                        "cards": str(row[2]).strip(),
                        "combo": str(row[3]).strip(),
                        "score_gained": safe_int(row[4]),
                        "final_score": safe_int(row[5])
                    })

            _HISTORY_CACHE = raw_history
            _HISTORY_CACHE_TIME = now
        except Exception as e:
            print(f"❌ เกิด Error ขณะดึง History จาก Sheets: {e}")
            return []

    if search_id:
        filtered = [h for h in raw_history if h["player_id"] == search_id]
        return filtered[:limit]

    return raw_history[:limit]
