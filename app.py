from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
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
# 🚪 LOGOUT ROUTE (เพิ่มเพื่อแก้ปัญหา 404 Not Found)
# -------------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    try:
        logout_player()
    except Exception as e:
        print(f"⚠️ Error during logout: {e}")
    return redirect("/login")


@app.route("/home")
def home():
    if "player_id" not in session:
        return redirect("/login")

    player_id = session.get("player_id")
    player = get_player_data(player_id) or {}

    total_score = player.get("total_score", 0)
    free_plays_used = player.get("free_plays_used", 0)

    return render_template(
        "home.html",
        player_id=player_id,
        player_name=session.get("player_name", "ผู้เล่น"),
        role=session.get("role"),
        event_luck=EVENT_LUCK,
        total_score=total_score,
        free_plays_used=free_plays_used
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
# 📊 ROUTE / RANKING (แก้ปัญหาหน้าขาวด้วยการส่ง leaderboard_data)
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

    # ดึงข้อมูลแยกตาม Role & ดวงกุด
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
# หน้าแสดงประวัติการเล่น (ดึงจาก SQLite)
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
        'G': 'Guard'
    }
    
    role_leaderboards = {code: [] for code in role_names.keys()}
    valid_players = []

    for p in all_players:
        if not p:
            continue

        # 📌 Helper Function ดึงค่าได้ทั้งแบบ dict และ object
        def get_val(key_list, default=''):
            if isinstance(p, dict):
                for k in key_list:
                    if k in p and p[k] is not None:
                        return p[k]
            else:
                for k in key_list:
                    if hasattr(p, k) and getattr(p, k) is not None:
                        return getattr(p, k)
            return default

        # 1. ดึงค่า "รหัสตัวละคร"
        char_id = str(get_val(['รหัสตัวละคร', 'character_id', 'player_id'], '')).strip().upper()

        # กรอง Admin ออกจาก Leaderboard
        if not char_id or char_id in [aid.upper() for aid in ADMIN_IDS]:
            continue

        # 2. ดึงค่า "Code name"
        code_name = str(get_val(['Code name', 'code_name', 'Code Name', 'ชื่อผู้เล่น'], char_id)).strip()

        # 3. ดึงค่า "คะแนน"
        score_val = get_val(['คะแนน', 'total_score', 'score'], 0)
        try:
            score_int = int(score_val)
        except (ValueError, TypeError):
            score_int = 0

        # 4. ดึงค่า "สายงาน"
        p_role = str(get_val(['สายงาน', 'role'], '')).strip()

        p_dict = {
            'character_id': char_id,  # ส่งไปใช้ในตารางช่อง "รหัสตัวละคร"
            'player_id': char_id,     # กัน fallback
            'code_name': code_name,    # ส่งไปใช้ในตารางช่อง "Code name"
            'player_name': code_name,
            'role': p_role,
            'total_score': score_int
        }
        valid_players.append(p_dict)

    # 1. Top 10 รวมทั้งหมด (Overall)
    overall_top10 = sorted(valid_players, key=lambda x: x['total_score'], reverse=True)[:10]

    # 2. Top 10 แต่ละ Role
    for code, full_name in role_names.items():
        role_players = [
            p for p in valid_players 
            if p['role'].upper() in [code.upper(), full_name.upper()] or p['character_id'].startswith(code.upper())
        ]
        role_leaderboards[code] = sorted(role_players, key=lambda x: x['total_score'], reverse=True)[:10]

    # 3. Top 10 แต้มต่ำสุด (ดวงกุด)
    worst_top10 = sorted(valid_players, key=lambda x: x['total_score'])[:10]

    return {
        "role_names": role_names,
        "overall_top10": overall_top10,
        "roles": role_leaderboards,
        "worst_top10": worst_top10
    }

if __name__ == "__main__":
    app.run(debug=True)
