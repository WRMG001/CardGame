from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime
from config import SECRET_KEY
from modules.auth import login_player, logout_player
# 🟢 เพิ่ม log_game_play และ get_player_history จาก game_service
from modules.game_service import play_game, get_db, log_game_play, get_player_history
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
# 2. API สุ่มไพ่ (โชว์แต้มดิบ + หัก -1 แต้มออกจาก Total Score)
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

        # 🔧 RESET สิทธิ์ประจำวัน
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

        # 2. สุ่มไพ่ผ่าน play_game
        result = play_game(player_id=player_id, event_luck=EVENT_LUCK, player_score=current_score)

        if not result.get("success"):
            return jsonify({"success": False, "message": result.get("message", "ไม่สามารถเล่นได้")})

        # 🟢 3. คำนวณแต้มดิบ และหักค่ากดเล่น -1 แต้มออกจาก Total Score
        raw_score = result.get("raw_score", result.get("score_gained", 0))  # แต้มคอมโบ ( High Card = 0, One Pair = 3 )
        PLAY_FEE = 1  # ค่าธรรมเนียมกดเล่น
        
        # คำนวณคะแนนรวมใหม่ (คะแนนเดิม + แต้มคอมโบ - ค่ากด 1)
        new_total_score = current_score + raw_score - PLAY_FEE
        
        new_free_plays_used = free_plays_used + 1
        new_plays_left = max(0, (DAILY_PLAY_LIMIT + bought_plays) - new_free_plays_used)

        # 4. บันทึกผลลัพธ์ย้อนกลับลง Google Sheets
        if player_sheet_info.get("sheet_name") and player_sheet_info.get("row_idx"):
            updated_data = {
                'total_score': new_total_score,  # บันทึกคะแนนรวมที่หัก -1 เรียบร้อยแล้ว
                'player_luck': result.get("next_player_luck", player_sheet_info.get("player_luck", 0.0)),
                'last_play_date': today_str,
                'free_plays_used': new_free_plays_used,
                'bought_plays_used': bought_plays
            }
            update_player_data(player_sheet_info["sheet_name"], player_sheet_info["row_idx"], updated_data)

        # ดึงชื่อคอมโบแบบยืดหยุ่น
        combo_title = result.get("combo") or result.get("combo_name") or "High Card"
        cards_str = ", ".join(result.get("cards", [])) if isinstance(result.get("cards"), list) else str(result.get("cards", ""))

        # 🟢 5.1 บันทึกประวัติลง SQLite (ส่ง raw_score ไปแสดงในประวัติ)
        try:
            log_game_play(
                player_id=player_id,
                cards=cards_str,
                combo=combo_title,
                score_gained=raw_score,  # บันทึกแต้มดิบลงประวัติ (0, 3, 5 ฯลฯ)
                final_score=new_total_score
            )
        except Exception as sqlite_err:
            print(f"⚠️ SQLite Log Warning: {sqlite_err}")

        # 🟢 5.2 บันทึกประวัติการเล่นลง Google Sheet "History"
        try:
            save_game_history(
                player_id=player_id,
                cards=result.get("cards", []),
                combo=combo_title,
                score_gained=raw_score,  # บันทึกแต้มดิบลงประวัติ Sheet
                final_score=new_total_score
            )
        except Exception as sheet_err:
            print(f"⚠️ Sheets Log Warning: {sheet_err}")

        session["total_score"] = new_total_score
        session["player_luck"] = result.get("next_player_luck", 0.0)

        # 🟢 6. ส่ง Response กลับไปแสดงผลฝั่งผู้เล่น
        return jsonify({
            "success": True,
            "cards": result["cards"],
            "combo": combo_title,
            "combo_name": combo_title,
            "score": raw_score,             # แสดงแต้มคอมโบดิบ (0, 3, 5)
            "score_gained": raw_score,      # แสดงแต้มคอมโบดิบ
            "total_score": new_total_score, # คะแนนรวมใหม่ที่หักค่ากด -1 แต้มแล้ว
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

    top_10_players = get_leaderboard(limit=15)
    
    try:
        all_players = get_all_players()
    except Exception as e:
        print(f"Error fetching all players: {e}")
        all_players = top_10_players

    filtered_all_players = [
        p for p in all_players 
        if str(p.get("player_id", "") if isinstance(p, dict) else getattr(p, "player_id", "")).strip().upper() not in [aid.upper() for aid in ADMIN_IDS]
    ]

    filtered_top_players = [
        p for p in top_10_players 
        if str(p.get("player_id", "") if isinstance(p, dict) else getattr(p, "player_id", "")).strip().upper() not in [aid.upper() for aid in ADMIN_IDS]
    ][:10]

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


# -------------------------------------------------------------
# 🟢 หน้าแสดงประวัติการเล่น (ดึงจาก SQLite)
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
                    if p.get("sheet_name") and p.get("row_idx"):
                        updated_data = {
                            'total_score': p.get("total_score", 0),
                            'player_luck': p.get("player_luck", 0.0),
                            'last_play_date': p.get("last_play_date", ""),
                            'free_plays_used': 0
                        }
                        update_player_data(p["sheet_name"], p["row_idx"], updated_data)
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


if __name__ == "__main__":
    app.run(debug=True)
