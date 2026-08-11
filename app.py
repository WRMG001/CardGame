from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
import re
from config import SECRET_KEY
from modules.auth import login_player, logout_player
from modules.game_service import play_game, get_db
from modules.score import calculate_score, SCORES
from modules.history import log_game_play, get_player_history
from modules.sheets_service import (
    update_player_data, 
    get_leaderboard, 
    get_player_data, 
    get_all_players,
    save_game_history,
    get_history_from_sheets
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 1. Admin IDs
ADMIN_IDS = ["ADMIN01", "ADMIN02", "ADMIN03"]

# 2. โควตาเล่นต่อวัน
DAILY_PLAY_LIMIT = 3

EVENT_LUCK = 0.0 
SHOW_LUCK_TO_PLAYERS = False

# ลำดับความสำคัญ/ความหายากของคอมโบสำหรับจัดอันดับ Top 5
COMBO_RANKING = {
    "Joker Trio": 100,
    "Royal Straight Flush": 80,
    "Royal Combo": 60,
    "Straight Flush": 50,
    "Three of a Kind": 15,
    "Straight": 10,
    "Flush": 5,
    "Double Joker 🃏🃏": 10,
    "Wild Triple 🎰": 8,
    "Wild Pair 🃏✨": 5,
    "One Pair": 3,
    "High Card": 0
}


@app.route("/")
def index():
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        player_id = request.form.get("player_id", "").strip().upper()
        if login_player(player_id):
            return redirect("/home")
        return render_template("login.html", error="ไม่พบ Player ID หรือรูปแบบรหัสไม่ถูกต้อง")
    return render_template("login.html")


# -------------------------------------------------------------
# 🚪 LOGOUT ROUTE
# -------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    try:
        logout_player()
    except Exception as e:
        print(f"⚠️ Error during logout: {e}")
    return redirect("/login")


# -------------------------------------------------------------
# 🏠 HOME ROUTE (ปรับปรุงการอ่าน List/Dict และการกรองวันที่)
# -------------------------------------------------------------
@app.route("/home")
def home():
    if "player_id" not in session:
        return redirect("/login")

    player_id = session.get("player_id")
    player = get_player_data(player_id) or {}

    total_score = player.get("total_score", 0)
    free_plays_used = player.get("free_plays_used", 0)

    # 📊 ดึงวันที่ปัจจุบัน
    now = datetime.now()
    today_iso = now.strftime("%Y-%m-%d")          # เช่น "2026-08-11"
    today_th = now.strftime("%d/%m/%Y")           # เช่น "11/08/2026"
    
    try:
        all_history = get_history_from_sheets() or []
    except Exception as e:
        print(f"⚠️ Error fetching history for home: {e}")
        all_history = []

    daily_scores = {}      # { player_id: total_score_today }
    player_names = {}      # { player_id: display_name }
    daily_combos = []      # รายการคอมโบประจำวัน

    for log in all_history:
        log_time = ""
        p_id = ""
        combo_name = "High Card"
        score_gained = 0

        # 1. รองรับข้อมูลกรณีเป็น List (เช่น [Timestamp, PlayerID, Cards, Combo, Score, TotalScore])
        if isinstance(log, (list, tuple)):
            if len(log) < 2:
                continue
            log_time = str(log[0]).strip()
            p_id = str(log[1]).strip().upper()
            combo_name = str(log[3]).strip() if len(log) > 3 else "High Card"
            try:
                score_gained = int(log[4]) if len(log) > 4 else 0
            except (ValueError, TypeError):
                score_gained = 0

        # 2. รองรับข้อมูลกรณีเป็น Dict
        elif isinstance(log, dict):
            p_id = str(
                log.get("player_id") or log.get("character_id") or 
                log.get("รหัสผู้เล่น") or log.get("รหัสตัวละคร") or log.get(1) or ""
            ).strip().upper()

            log_time = str(
                log.get("timestamp") or log.get("created_at") or 
                log.get("date") or log.get("เวลา") or log.get("วันที่") or log.get(0) or ""
            ).strip()

            combo_name = str(
                log.get("combo") or log.get("combo_name") or 
                log.get("คอมโบ") or log.get(3) or "High Card"
            ).strip()

            score_val = (
                log.get("score_gained") or log.get("score") or 
                log.get("คะแนนที่ได้") or log.get("คะแนน") or log.get(4) or 0
            )
            try:
                score_gained = int(score_val)
            except (ValueError, TypeError):
                score_gained = 0

        else:
            continue

        # ข้าม Admin และรหัสว่าง
        if not p_id or p_id in [aid.upper() for aid in ADMIN_IDS]:
            continue

        # 3. ตรวจสอบวันที่ (ตัดเอาเฉพาะ YYYY-MM-DD มาเทียบ)
        is_today = False
        if log_time:
            # ดึงเฉพาะส่วนวันที่ เช่น "2026-08-11" จาก "2026-08-11 03:39:09"
            log_date_part = log_time.split(" ")[0]
            if log_date_part == today_iso or today_iso in log_time or today_th in log_time:
                is_today = True
        else:
            is_today = True

        if not is_today:
            continue

        # 4. ดึงชื่อผู้เล่น
        p_data = get_player_data(p_id) or {}
        p_name = p_data.get("player_name") or p_data.get("code_name") or p_id
        player_names[p_id] = p_name

        # 5. รวมคะแนนและคอมโบ
        daily_scores[p_id] = daily_scores.get(p_id, 0) + score_gained

        combo_weight = COMBO_RANKING.get(combo_name, 0)
        daily_combos.append({
            "player_id": p_id,
            "player_name": p_name,
            "combo": combo_name,
            "combo_weight": combo_weight,
            "score_gained": score_gained,
            "timestamp": log_time
        })

    # จัดอันดับ Top 10 คะแนนสูงสุดประจำวัน
    top10_daily = []
    sorted_daily_scores = sorted(daily_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    for p_id, score in sorted_daily_scores:
        top10_daily.append({
            "player_id": p_id,
            "player_name": player_names.get(p_id, p_id),
            "score_today": score
        })

    # จัดอันดับ Top 5 คอมโบสูงสุดประจำวัน
    sorted_combos = sorted(daily_combos, key=lambda x: (x["combo_weight"], x["score_gained"]), reverse=True)[:5]

    return render_template(
        "home.html",
        player_id=player_id,
        player_name=session.get("player_name", "ผู้เล่น"),
        role=session.get("role"),
        event_luck=EVENT_LUCK,
        total_score=total_score,
        free_plays_used=free_plays_used,
        top10_daily=top10_daily,
        top5_combos=sorted_combos
    )

# -------------------------------------------------------------
# 1. หน้าเกมหลัก
# -------------------------------------------------------------
@app.route("/game")
def game():
    if "player_id" not in session:
        return redirect("/login")

    player_id = str(session.get("player_id", "")).strip().upper()
    player_name = session.get("player_name", "ผู้เล่น")
    
    plays_left = 0
    total_score = 0
    player_luck = 0.0

    # ดึงข้อมูลจาก Google Sheets
    player_sheet_info = get_player_data(player_id)
    
    if player_sheet_info:
        total_score = player_sheet_info.get("total_score", 0)
        player_luck = player_sheet_info.get("player_luck", 0.0)
        
        free_plays_used = player_sheet_info.get("free_plays_used", 0)
        bought_plays = player_sheet_info.get("bought_plays_used", 0)
        plays_left = max(0, (DAILY_PLAY_LIMIT + bought_plays) - free_plays_used)
    else:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT daily_free, score, player_luck FROM players WHERE player_id = ?", (player_id,))
            player = cursor.fetchone()
            conn.close()

            if player:
                plays_left = player["daily_free"]
                total_score = player["score"]
                player_luck = player["player_luck"]
        except Exception as e:
            print(f"Error getting player db data: {e}")

    if plays_left <= 0:
        return render_template(
            "game_limit.html",
            player_id=player_id,
            player_name=player_name,
            max_limit=DAILY_PLAY_LIMIT,
            total_score=total_score
        )

    return render_template(
        "game.html",
        player_id=player_id,
        player_name=player_name,
        plays_left=plays_left,
        total_score=total_score,
        show_luck=SHOW_LUCK_TO_PLAYERS,
        final_luck=round(player_luck + EVENT_LUCK, 2)
    )


# -------------------------------------------------------------
# 2. API สุ่มไพ่
# -------------------------------------------------------------
SCORE_MAP = {
    "Joker Trio": 100,
    "Royal Straight Flush": 80,
    "Royal Combo": 60,
    "Straight Flush": 50,
    "Three of a Kind": 15,
    "Straight": 10,
    "Flush": 5,
    "One Pair": 3,
    "High Card": 0,
    "Double Joker 🃏🃏": 10,
    "Wild Triple 🎰": 8,
    "Wild Pair 🃏✨": 5
}

@app.route("/api/play", methods=["POST"])
def api_play():
    if "player_id" not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบก่อนเล่น"}), 401

    player_id = str(session.get("player_id", "")).strip().upper()

    try:
        player_sheet_info = get_player_data(player_id)
        if not player_sheet_info:
            return jsonify({"success": False, "message": "ไม่พบข้อมูลผู้เล่นในระบบ Google Sheets"}), 400

        today_str = datetime.now().strftime("%Y-%m-%d")
        last_play_date = player_sheet_info.get("last_play_date", "")

        if last_play_date != today_str:
            free_plays_used = 0
            bought_plays = 0
        else:
            free_plays_used = player_sheet_info.get("free_plays_used", 0)
            bought_plays = player_sheet_info.get("bought_plays_used", 0)

        try:
            current_score = int(player_sheet_info.get("total_score", 0))
        except (ValueError, TypeError):
            current_score = 0
        
        plays_left = max(0, (DAILY_PLAY_LIMIT + bought_plays) - free_plays_used)
        if plays_left <= 0:
            return jsonify({"success": False, "message": "สิทธิ์การเล่นของคุณหมดแล้ววันนี้"}), 400

        current_luck = player_sheet_info.get("player_luck", 0.0)
        result = play_game(player_id=player_id, player_luck=current_luck, event_luck=EVENT_LUCK)

        if not result.get("success"):
            return jsonify({"success": False, "message": "ไม่สามารถเล่นได้"})

        combo_title = result.get("combo") or result.get("combo_name") or "High Card"
        score_calc = calculate_score(combo_title, current_score)

        raw_score = score_calc["raw_score"]
        net_score_gained = score_calc["score_gained"]
        new_total_score = score_calc["final_score"]

        new_free_plays_used = free_plays_used + 1
        new_plays_left = max(0, (DAILY_PLAY_LIMIT + bought_plays) - new_free_plays_used)

        if player_sheet_info.get("sheet_name") and player_sheet_info.get("row_idx"):
            updated_data = {
                'total_score': new_total_score,
                'player_luck': result.get("next_player_luck", current_luck),
                'last_play_date': today_str,
                'free_plays_used': new_free_plays_used,
                'bought_plays_used': bought_plays
            }
            update_player_data(player_sheet_info["sheet_name"], player_sheet_info["row_idx"], updated_data)

        try:
            log_game_play(
                player_id=player_id,
                cards=result.get("cards", []),
                combo_name=combo_title,
                score_gained=net_score_gained,
                final_score=new_total_score
            )
            save_game_history(
                player_id=player_id,
                cards=result.get("cards", []),
                combo=combo_title,
                score_gained=net_score_gained,
                final_score=new_total_score
            )
        except Exception as log_err:
            print(f"⚠️ Log Warning: {log_err}")

        session["total_score"] = new_total_score
        session["player_luck"] = result.get("next_player_luck", 0.0)

        return jsonify({
            "success": True,
            "cards": result["cards"],
            "combo": combo_title,
            "combo_name": combo_title,
            "raw_score": raw_score,
            "score_gained": net_score_gained,
            "total_score": new_total_score, 
            "plays_left": new_plays_left,
            "remaining_spins": new_plays_left
        })
    except Exception as e:
        print(f"❌ Play API Error: {e}")
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}), 500


# -------------------------------------------------------------
# 📊 ROUTE / RANKING
# -------------------------------------------------------------
@app.route("/ranking")
def ranking():
    if "player_id" not in session:
        return redirect("/login")

    try:
        top_10_players = get_leaderboard(limit=15) or []
    except Exception as e:
        print(f"⚠️ Error get_leaderboard: {e}")
        top_10_players = []

    try:
        all_players = get_all_players() or []
    except Exception as e:
        print(f"⚠️ Error fetching all players: {e}")
        all_players = top_10_players

    # กรอง Admin ออก
    filtered_all_players = []
    for p in all_players:
        if not p:
            continue
        p_id = str(p.get("player_id", "") if isinstance(p, dict) else getattr(p, "player_id", "")).strip().upper()
        if p_id not in [aid.upper() for aid in ADMIN_IDS]:
            filtered_all_players.append(p)

    filtered_top_players = filtered_all_players[:10]

    # จัดกลุ่มตาม Sheet Name
    grouped_players = {}
    for p in filtered_all_players:
        sheet_name = p.get("sheet_name") if isinstance(p, dict) else getattr(p, "sheet_name", "ผู้เล่นทั้งหมด")
        if not sheet_name:
            sheet_name = "ผู้เล่นทั้งหมด"
            
        if sheet_name not in grouped_players:
            grouped_players[sheet_name] = []
        grouped_players[sheet_name].append(p)

    leaderboard_roles_data = {}
    try:
        leaderboard_roles_data = get_leaderboards_by_role()
    except Exception as e:
        print(f"⚠️ Error get_leaderboards_by_role: {e}")

    return render_template(
        "ranking.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name"),
        top_players=filtered_top_players,
        grouped_players=grouped_players,
        leaderboard_data=leaderboard_roles_data
    )


# -------------------------------------------------------------
# หน้าแสดงประวัติการเล่น
# -------------------------------------------------------------
@app.route("/history")
def history():
    if "player_id" not in session:
        return redirect("/login")

    player_id = str(session.get("player_id", "")).strip().upper()
    player_name = session.get("player_name", "ผู้เล่น")
    
    try:
        history_logs = get_player_history(player_id, limit=20)
    except Exception as e:
        print(f"Error reading history from DB: {e}")
        history_logs = []

    return render_template(
        "history.html",
        player_id=player_id,
        player_name=player_name,
        history_logs=history_logs
    )


# -------------------------------------------------------------
# 3. Admin Dashboard
# -------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    global EVENT_LUCK, SHOW_LUCK_TO_PLAYERS

    if "player_id" not in session:
        return redirect("/login")

    current_player_id = str(session.get("player_id", "")).strip().upper()
    current_role = str(session.get("role", "")).lower()

    if current_role != "admin" and current_player_id not in [aid.upper() for aid in ADMIN_IDS]:
        return redirect("/home")

    msg = None
    searched_player = None

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_event":
            try:
                EVENT_LUCK = float(request.form.get("event_luck", 0.0))
                SHOW_LUCK_TO_PLAYERS = "show_luck" in request.form
                msg = "✅ อัปเดตค่า Event สำเร็จ!"
            except ValueError:
                msg = "❌ กรุณากรอกตัวเลขค่า Luck"

        elif action == "search_player":
            target_id = request.form.get("target_player_id", "").strip().upper()
            searched_player = get_player_data(target_id)
            if not searched_player:
                msg = f"❌ ไม่พบรหัสผู้เล่น {target_id}"

        elif action == "modify_score":
            target_id = request.form.get("target_player_id", "").strip().upper()
            try:
                score_change = int(request.form.get("score_change", 0))
                
                player_info = get_player_data(target_id)
                if player_info and player_info.get("sheet_name") and player_info.get("row_idx"):
                    new_score = int(player_info.get("total_score", 0)) + score_change
                    updated_data = {
                        'total_score': new_score,
                        'player_luck': player_info.get("player_luck", 0.0),
                        'last_play_date': player_info.get("last_play_date", ""),
                        'free_plays_used': player_info.get("free_plays_used", 0)
                    }
                    update_player_data(player_info["sheet_name"], player_info["row_idx"], updated_data)

                msg = f"✅ ปรับคะแนนของ {target_id} สำเร็จ!"
                searched_player = get_player_data(target_id)
            except Exception as e:
                msg = f"❌ เกิดข้อผิดพลาด: {str(e)}"

        elif action == "reset_limit":
            target_id = request.form.get("target_player_id", "").strip().upper()
            try:
                player_info = get_player_data(target_id)
                if player_info and player_info.get("sheet_name") and player_info.get("row_idx"):
                    updated_data = {
                        'total_score': player_info.get("total_score", 0),
                        'player_luck': player_info.get("player_luck", 0.0),
                        'last_play_date': player_info.get("last_play_date", ""),
                        'free_plays_used': 0
                    }
                    update_player_data(player_info["sheet_name"], player_info["row_idx"], updated_data)

                msg = f"✅ รีเซ็ตสิทธิ์ของ {target_id} เป็น {DAILY_PLAY_LIMIT} รอบเรียบร้อย!"
                searched_player = get_player_data(target_id)
            except Exception as e:
                msg = f"❌ เกิดข้อผิดพลาดในการรีเซ็ต: {str(e)}"

        elif action == "reset_all_limits":
            try:
                all_players = get_all_players()
                count = 0
                for p in all_players:
                    s_name = p.get("sheet_name") if isinstance(p, dict) else getattr(p, "sheet_name", None)
                    r_idx = p.get("row_idx") if isinstance(p, dict) else getattr(p, "row_idx", None)
                    t_score = p.get("total_score", 0) if isinstance(p, dict) else getattr(p, "total_score", 0)
                    p_luck = p.get("player_luck", 0.0) if isinstance(p, dict) else getattr(p, "player_luck", 0.0)
                    l_date = p.get("last_play_date", "") if isinstance(p, dict) else getattr(p, "last_play_date", "")

                    if s_name and r_idx:
                        updated_data = {
                            'total_score': t_score,
                            'player_luck': p_luck,
                            'last_play_date': l_date,
                            'free_plays_used': 0
                        }
                        update_player_data(s_name, r_idx, updated_data)
                        count += 1

                msg = f"🎉 รีเซ็ตสิทธิ์การเล่นของผู้เล่นทุกคนสำเร็จ! (ทั้งหมด {count} คน)"
            except Exception as e:
                msg = f"❌ เกิดข้อผิดพลาดในการรีเซ็ตทั้งหมด: {str(e)}"

    try:
        return render_template(
            "admin.html",
            event_luck=EVENT_LUCK,
            show_luck=SHOW_LUCK_TO_PLAYERS,
            msg=msg,
            searched_player=searched_player
        )
    except Exception:
        return render_template(
            "dashboard.html",
            event_luck=EVENT_LUCK,
            show_luck=SHOW_LUCK_TO_PLAYERS,
            msg=msg,
            searched_player=searched_player
        )


# -------------------------------------------------------------
# 📊 ROUTE / API สำหรับ LEADERBOARD
# -------------------------------------------------------------
@app.route("/api/leaderboard/roles")
def api_leaderboard_roles():
    if "player_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        data = get_leaderboards_by_role()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        print(f"❌ Leaderboard API Error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/leaderboard-roles")
def leaderboard_roles_page():
    if "player_id" not in session:
        return redirect("/login")
        
    leaderboard_data = get_leaderboards_by_role()
    return render_template(
        "leaderboard_roles.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name"),
        role_names=leaderboard_data["role_names"],
        roles_data=leaderboard_data["roles"],
        worst_top10=leaderboard_data["worst_top10"]
    )


# ==========================================
# 📊 LEADERBOARD HELPER FUNCTIONS
# ==========================================

def get_all_players_data():
    try:
        players = get_all_players()
        return players if players else []
    except Exception as e:
        print(f"⚠️ Error fetching all players: {e}")
        return []


def get_leaderboards_by_role():
    all_players = get_all_players_data()
    
    role_names = {
        'C': 'Customer',
        'P': 'Partner',
        'H': 'Host',
        'BL': 'Black',
        'BA': 'Bartender',
        'W': 'Waiter',
        'G': 'Guard',
        'O': 'Owner'
    }
    
    role_leaderboards = {code: [] for code in role_names.keys()}
    valid_players = []

    for p in all_players:
        if not p:
            continue

        clean_p = {}
        if isinstance(p, dict):
            clean_p = {str(k).strip().lower().replace(" ", "_"): v for k, v in p.items()}
        elif hasattr(p, '__dict__'):
            clean_p = {str(k).strip().lower().replace(" ", "_"): v for k, v in p.__dict__.items()}

        def get_val(target_keys, default=''):
            for tk in target_keys:
                clean_tk = tk.strip().lower().replace(" ", "_")
                if clean_tk in clean_p and clean_p[clean_tk] is not None:
                    val = str(clean_p[clean_tk]).strip()
                    if val != '':
                        return clean_p[clean_tk]
            return default

        char_id = str(get_val(['รหัสตัวละคร', 'character_id', 'player_id', 'id'], '')).strip().upper()

        if not char_id or char_id in [aid.upper() for aid in ADMIN_IDS]:
            continue

        code_name = str(get_val(['code_name', 'codename', 'code name', 'name', 'ชื่อ'], '')).strip()
        if not code_name:
            code_name = char_id

        score_val = get_val(['total_score', 'score', 'คะแนน', 'total score'], 0)
        try:
            score_int = int(score_val)
        except (ValueError, TypeError):
            score_int = 0

        p_role = str(get_val(['role', 'สายงาน'], '')).strip().upper()
        if not p_role:
            match = re.match(r"^([A-Z]+)", char_id)
            p_role = match.group(1) if match else ''

        p_dict = {
            'character_id': char_id,
            'player_id': char_id,
            'code_name': code_name,
            'player_name': code_name,
            'role': p_role,
            'total_score': score_int
        }
        valid_players.append(p_dict)

    overall_top10 = sorted(valid_players, key=lambda x: x['total_score'], reverse=True)[:10]

    for code, full_name in role_names.items():
        role_players = [
            p for p in valid_players 
            if p['role'] == code or p['character_id'].startswith(code)
        ]
        role_leaderboards[code] = sorted(role_players, key=lambda x: x['total_score'], reverse=True)[:10]

    worst_top10 = sorted(valid_players, key=lambda x: x['total_score'])[:10]

    return {
        "role_names": role_names,
        "overall_top10": overall_top10,
        "roles": role_leaderboards,
        "worst_top10": worst_top10
    }


def get_grouped_players():
    all_players = get_all_players_data()
    
    role_names = {
        'C': 'Customer',
        'P': 'Partner',
        'H': 'Host',
        'BL': 'Black',
        'BA': 'Bartender',
        'W': 'Waiter',
        'G': 'Guard',
        'O': 'Owner'
    }
    
    grouped = {full_name: [] for full_name in role_names.values()}
    
    for p in all_players:
        if not p:
            continue

        clean_p = {}
        if isinstance(p, dict):
            clean_p = {str(k).strip().lower().replace(" ", "_"): v for k, v in p.items()}
        elif hasattr(p, '__dict__'):
            clean_p = {str(k).strip().lower().replace(" ", "_"): v for k, v in p.__dict__.items()}

        def get_val(target_keys, default=''):
            for tk in target_keys:
                clean_tk = tk.strip().lower().replace(" ", "_")
                if clean_tk in clean_p and clean_p[clean_tk] is not None:
                    val = str(clean_p[clean_tk]).strip()
                    if val != '':
                        return clean_p[clean_tk]
            return default

        char_id = str(get_val(['รหัสตัวละคร', 'character_id', 'player_id', 'id'], '')).strip().upper()
        if not char_id or char_id in [aid.upper() for aid in ADMIN_IDS]:
            continue

        code_name = str(get_val(['code_name', 'codename', 'code name', 'name', 'ชื่อ'], '')).strip()
        if not code_name:
            code_name = char_id

        score_val = get_val(['total_score', 'score', 'คะแนน', 'total score'], 0)
        try:
            score_int = int(score_val)
        except (ValueError, TypeError):
            score_int = 0

        p_role = str(get_val(['role', 'สายงาน'], '')).strip().upper()
        if not p_role:
            match = re.match(r"^([A-Z]+)", char_id)
            p_role = match.group(1) if match else ''

        player_dict = {
            'character_id': char_id,
            'player_id': char_id,
            'code_name': code_name,
            'total_score': score_int,
            'role': p_role
        }

        role_full_name = role_names.get(p_role, 'อื่นๆ')
        if role_full_name in grouped:
            grouped[role_full_name].append(player_dict)
        else:
            grouped.setdefault(role_full_name, []).append(player_dict)

    return grouped


if __name__ == "__main__":
    app.run(debug=True)
