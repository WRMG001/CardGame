from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
from modules.history import log_game_play
from config import SECRET_KEY
from modules.auth import login_player, logout_player
from modules.game_service import play_game, get_db
from modules.sheets_service import update_player_data, get_leaderboard, get_player_data, get_all_players
from modules.history import get_player_history

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


@app.route("/home")
def home():
    if "player_id" not in session:
        return redirect("/login")

    return render_template(
        "home.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name", "ผู้เล่น"),
        role=session.get("role"),
        event_luck=EVENT_LUCK
    )


@app.route("/logout")
def logout():
    logout_player()
    return redirect("/")


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
        bought_plays = player_sheet_info.get("bought_plays", 0)
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
# 2. API สุ่มไพ่ (ตัดสิทธิ์ + เซฟลง Google Sheet + บันทึกประวัติ)
# -------------------------------------------------------------
@app.route("/api/play", methods=["POST"])
def api_play():
    if "player_id" not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบก่อนเล่น"}), 401

    player_id = str(session.get("player_id", "")).strip().upper()

    try:
        # 1. อ่านข้อมูลผู้เล่นปัจจุบันจาก Google Sheet
        player_sheet_info = get_player_data(player_id)
        if not player_sheet_info:
            return jsonify({"success": False, "message": "ไม่พบข้อมูลผู้เล่นในระบบ Google Sheets"}), 400

        today_str = datetime.now().strftime("%Y-%m-%d")
        last_play_date = player_sheet_info.get("last_play_date", "")

        # 🔧 [FIX 1: RESET สิทธิ์ประจำวัน]
        # ถ้าวันที่ล่าสุดใน Sheet ไม่ใช่วันนี้ ให้รีเซ็ตจำนวนสิทธิ์ที่ใช้ไปเป็น 0
        if last_play_date != today_str:
            free_plays_used = 0
            bought_plays = 0
        else:
            free_plays_used = player_sheet_info.get("free_plays_used", 0)
            bought_plays = player_sheet_info.get("bought_plays_used", 0)

        current_score = player_sheet_info.get("total_score", 0)
        
        # เช็กสิทธิ์คงเหลือ
        plays_left = max(0, (DAILY_PLAY_LIMIT + bought_plays) - free_plays_used)
        if plays_left <= 0:
            return jsonify({"success": False, "message": "สิทธิ์การเล่นของคุณหมดแล้ววันนี้"}), 400

        # 2. สุ่มไพ่และคำนวณผลผ่าน play_game
        result = play_game(player_id=player_id, event_luck=EVENT_LUCK, player_score=current_score)

        if not result.get("success"):
            return jsonify({"success": False, "message": result.get("message", "ไม่สามารถเล่นได้")})

        # 3. คำนวณคะแนนและสิทธิ์เล่นใหม่
        score_gained = result.get("score_gained", 0)
        new_total_score = current_score + score_gained
        new_free_plays_used = free_plays_used + 1
        new_plays_left = max(0, (DAILY_PLAY_LIMIT + bought_plays) - new_free_plays_used)

        # 4. บันทึกผลลัพธ์ย้อนกลับลง Google Sheets
        if player_sheet_info.get("sheet_name") and player_sheet_info.get("row_idx"):
            updated_data = {
                'total_score': new_total_score,
                'player_luck': result.get("next_player_luck", player_sheet_info.get("player_luck", 0.0)),
                'last_play_date': today_str,
                'free_plays_used': new_free_plays_used,
                'bought_plays_used': bought_plays
            }
            update_player_data(player_sheet_info["sheet_name"], player_sheet_info["row_idx"], updated_data)

        # ดึงชื่อคอมโบแบบยืดหยุ่น
        combo_title = result.get("combo") or result.get("combo_name") or "High Card"

        # 🔧 [FIX 2: บันทึกประวัติการเล่นลง SQLite]
        log_game_play(
            player_id=player_id,
            cards=result.get("cards", []),
            combo_name=combo_title,
            score_gained=score_gained,
            final_score=new_total_score
        )

        # 5. บันทึกลง SQLite DB เป็น Backup สำรอง
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE players SET score = ?, player_luck = ?, last_play_date = ? WHERE player_id = ?",
                (new_total_score, result.get("next_player_luck", 0.0), today_str, player_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ SQLite Update Error: {e}")

        session["total_score"] = new_total_score
        session["player_luck"] = result.get("next_player_luck", 0.0)

        return jsonify({
            "success": True,
            "cards": result["cards"],
            "combo": combo_title,
            "combo_name": combo_title,
            "score": score_gained,
            "score_gained": score_gained,
            "total_score": new_total_score,
            "plays_left": new_plays_left,
            "remaining_spins": new_plays_left
        })

    except Exception as e:
        print(f"❌ Play API Error: {e}")
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}), 500

@app.route("/ranking")
def ranking():
    if "player_id" not in session:
        return redirect("/login")

    # 1. ดึงข้อมูลรายชื่อและตารางอันดับ
    top_10_players = get_leaderboard(limit=15)
    
    try:
        all_players = get_all_players()
    except Exception as e:
        print(f"Error fetching all players: {e}")
        all_players = top_10_players

    # 2. กรองรหัส ADMIN ออกทั้งหมด ไม่ให้แสดงในตาราง
    filtered_all_players = [
        p for p in all_players 
        if str(p.get("player_id", "") if isinstance(p, dict) else getattr(p, "player_id", "")).strip().upper() not in [aid.upper() for aid in ADMIN_IDS]
    ]

    filtered_top_players = [
        p for p in top_10_players 
        if str(p.get("player_id", "") if isinstance(p, dict) else getattr(p, "player_id", "")).strip().upper() not in [aid.upper() for aid in ADMIN_IDS]
    ][:10]

    # 3. จัดกลุ่มผู้เล่นแยกตาม Sheet Name
    grouped_players = {}
    for p in filtered_all_players:
        sheet_name = p.get("sheet_name") if isinstance(p, dict) else getattr(p, "sheet_name", "ผู้เล่นทั้งหมด")
        if not sheet_name:
            sheet_name = "ผู้เล่นทั้งหมด"
            
        if sheet_name not in grouped_players:
            grouped_players[sheet_name] = []
        grouped_players[sheet_name].append(p)

    return render_template(
        "ranking.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name"),
        top_players=filtered_top_players,
        grouped_players=grouped_players
    )


@app.route("/history")
def history():
    if "player_id" not in session:
        return redirect("/login")

    player_id = str(session.get("player_id", "")).strip().upper()
    player_name = session.get("player_name", "ผู้เล่น")
    
    history_logs = get_player_history(player_id, limit=20)

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
                
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE players SET score = score + ? WHERE player_id = ?", (score_change, target_id))
                conn.commit()
                conn.close()

                player_info = get_player_data(target_id)
                if player_info and player_info.get("sheet_name") and player_info.get("row_idx"):
                    new_score = player_info.get("total_score", 0) + score_change
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
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE players SET daily_free = ?, today_play = 0 WHERE player_id = ?", (DAILY_PLAY_LIMIT, target_id))
                conn.commit()
                conn.close()

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
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE players SET daily_free = ?, today_play = 0", (DAILY_PLAY_LIMIT,))
                affected_rows = cursor.rowcount
                conn.commit()
                conn.close()

                all_players = get_all_players()
                for p in all_players:
                    if p.get("sheet_name") and p.get("row_idx"):
                        updated_data = {
                            'total_score': p.get("total_score", 0),
                            'player_luck': p.get("player_luck", 0.0),
                            'last_play_date': p.get("last_play_date", ""),
                            'free_plays_used': 0
                        }
                        update_player_data(p["sheet_name"], p["row_idx"], updated_data)

                msg = f"🎉 รีเซ็ตสิทธิ์การเล่นของผู้เล่นทุกคนสำเร็จ! (ทั้งหมด {affected_rows} คน)"
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


if __name__ == "__main__":
    app.run(debug=True)
