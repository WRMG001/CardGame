from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from datetime import datetime

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
DAILY_PLAY_LIMIT = 2    # สอดคล้องกับ daily_free ใน game_service.py

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
        show_luck=SHOW_LUCK_TO_PLAYERS,
        final_luck=round(player_luck + EVENT_LUCK, 2)
    )


# -------------------------------------------------------------
# 2. API สุ่มไพ่
# -------------------------------------------------------------
@app.route("/api/play", methods=["POST"])
def api_play():
    if "player_id" not in session:
        return jsonify({"success": False, "message": "กรุณาเข้าสู่ระบบก่อนเล่น"}), 401

    player_id = str(session.get("player_id", "")).strip().upper()

    try:
        result = play_game(player_id=player_id, event_luck=EVENT_LUCK)

        if not result.get("success"):
            return jsonify({"success": False, "message": result.get("message", "ไม่สามารถเล่นได้")})

        plays_left = 0
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT daily_free FROM players WHERE player_id = ?", (player_id,))
            p = cursor.fetchone()
            conn.close()
            if p:
                plays_left = p["daily_free"]
        except Exception:
            pass

        session["total_score"] = result["final_score"]
        session["player_luck"] = result["next_player_luck"]

        return jsonify({
            "success": True,
            "cards": result["cards"],
            "combo": result["combo"],
            "score_gained": result["score_gained"],
            "total_score": result["final_score"],
            "plays_left": plays_left
        })

    except Exception as e:
        print(f"❌ Play API Error: {e}")
        return jsonify({"success": False, "message": f"เกิดข้อผิดพลาด: {str(e)}"}), 500


@app.route("/ranking")
def ranking():
    if "player_id" not in session:
        return redirect("/login")

    top_10_players = get_leaderboard(limit=10)
    
    try:
        all_players = get_all_players()
    except Exception as e:
        print(f"Error fetching all players: {e}")
        all_players = top_10_players

    return render_template(
        "ranking.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name"),
        top_players=top_10_players,
        all_players=all_players
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
# 3. Admin Dashboard (จัดการสิทธิ์และแก้ไขข้อมูลผู้เล่นอื่น)
# -------------------------------------------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    global EVENT_LUCK, SHOW_LUCK_TO_PLAYERS

    if "player_id" not in session:
        return redirect("/login")

    current_player_id = str(session.get("player_id", "")).strip().upper()
    if current_player_id not in [aid.upper() for aid in ADMIN_IDS]:
        return redirect("/home")

    msg = None
    searched_player = None

    if request.method == "POST":
        action = request.form.get("action")
        
        # --- อัปเดตกิจกรรม/ค่า Luck ของเซิร์ฟเวอร์ ---
        if action == "update_event":
            try:
                EVENT_LUCK = float(request.form.get("event_luck", 0.0))
                SHOW_LUCK_TO_PLAYERS = "show_luck" in request.form
                msg = "✅ อัปเดตค่า Event สำเร็จ!"
            except ValueError:
                msg = "❌ กรุณากรอกตัวเลขค่า Luck"

        # --- ค้นหาข้อมูลผู้เล่น ---
        elif action == "search_player":
            target_id = request.form.get("target_player_id", "").strip().upper()
            searched_player = get_player_data(target_id)
            if not searched_player:
                msg = f"❌ ไม่พบรหัสผู้เล่น {target_id}"

        # --- ปรับแต่งคะแนนผู้เล่น ---
        elif action == "modify_score":
            target_id = request.form.get("target_player_id", "").strip().upper()
            try:
                score_change = int(request.form.get("score_change", 0))
                
                # 1. อัปเดตใน SQLite
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE players SET score = score + ? WHERE player_id = ?", (score_change, target_id))
                conn.commit()
                conn.close()

                # 2. อัปเดตใน Google Sheets
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

        # --- รีเซ็ตสิทธิ์ผู้เล่นแบบระบุคน (Specific Player) ---
        elif action == "reset_limit":
            target_id = request.form.get("target_player_id", "").strip().upper()
            try:
                # 1. อัปเดตใน SQLite DB
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE players SET daily_free = ?, today_play = 0 WHERE player_id = ?", (DAILY_PLAY_LIMIT, target_id))
                conn.commit()
                conn.close()

                # 2. อัปเดตใน Google Sheets
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

        # --- รีเซ็ตสิทธิ์ผู้เล่นทุกคนทั้งระบบ (Reset All Players) ---
        elif action == "reset_all_limits":
            try:
                # รีเซ็ตสิทธิ์ทุกคนใน SQLite DB
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute("UPDATE players SET daily_free = ?, today_play = 0", (DAILY_PLAY_LIMIT,))
                affected_rows = cursor.rowcount
                conn.commit()
                conn.close()

                msg = f"🎉 รีเซ็ตสิทธิ์การเล่นให้ผู้เล่นทุกคนเป็น {DAILY_PLAY_LIMIT} รอบสำเร็จ! (ทั้งหมด {affected_rows} คน)"
            except Exception as e:
                msg = f"❌ เกิดข้อผิดพลาดในการรีเซ็ตทั้งหมด: {str(e)}"

    template_to_render = "dashboard.html"
    try:
        return render_template(
            template_to_render,
            event_luck=EVENT_LUCK,
            show_luck=SHOW_LUCK_TO_PLAYERS,
            msg=msg,
            searched_player=searched_player
        )
    except Exception:
        return render_template(
            "admin.html",
            event_luck=EVENT_LUCK,
            show_luck=SHOW_LUCK_TO_PLAYERS,
            msg=msg,
            searched_player=searched_player
        )


if __name__ == "__main__":
    app.run(debug=True)
