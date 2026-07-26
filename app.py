from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime

from config import SECRET_KEY
from modules.auth import login_player, logout_player
from modules.game_service import play_game
from modules.sheets_service import update_player_data, get_leaderboard, get_player_data
from modules.history import log_game_play, get_player_history

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ID ผู้เล่นที่มีสิทธิ์ Admin
ADMIN_IDS = ["ADMIN01", "P001", "H001"]

# กำหนดจำนวนรอบฟรีต่อวัน
DAILY_FREE_LIMIT = 5

EVENT_LUCK = 0.0 
SHOW_LUCK_TO_PLAYERS = False


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        player_id = request.form.get("player_id", "")

        if login_player(player_id):
            return redirect("/home")

        return render_template(
            "login.html",
            error="ไม่พบ Player ID หรือรูปแบบรหัสไม่ถูกต้อง"
        )

    return render_template("login.html")


@app.route("/home")
def home():
    if "player_id" not in session:
        return redirect("/login")

    return render_template(
        "home.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name"),
        role=session.get("role"),
        event_luck=EVENT_LUCK
    )


@app.route("/logout")
def logout():
    logout_player()
    return redirect("/")


@app.route("/game")
def game():
    if "player_id" not in session:
        return redirect("/login")

    player_id = session.get("player_id")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    last_play_date = session.get("last_play_date", "")
    free_plays_used = session.get("free_plays_used", 0)

    # 🛑 เช็กถ้าเป็นวันใหม่ ให้รีเซ็ตจำนวนรอบที่เล่นไปแล้ว
    if last_play_date != today_str:
        free_plays_used = 0
        session["last_play_date"] = today_str
        session["free_plays_used"] = 0

    # 🛑 เช็กว่ารอบเล่นฟรีเกินโควตาประจำวันหรือยัง
    if free_plays_used >= DAILY_FREE_LIMIT:
        return render_template(
            "game_limit.html",
            player_id=player_id,
            player_name=session.get("player_name"),
            max_limit=DAILY_FREE_LIMIT
        )

    player_luck = session.get("player_luck", 0.0)

    # 1. เล่นเกมสุ่มไพ่
    result = play_game(player_luck=player_luck, event_luck=EVENT_LUCK)

    # 2. เพิ่มจำนวนรอบที่เล่นและอัปเดต Session
    free_plays_used += 1
    session["free_plays_used"] = free_plays_used
    session["player_luck"] = result["next_player_luck"]

    # 3. บันทึกผลลง Google Sheet และอัปเดต Session Real-time
    sheet_name = session.get("sheet_name")
    row_idx = session.get("row_idx")

    if sheet_name and row_idx:
        current_total = session.get("total_score", 0)
        new_total = current_total + result["final_score"]
        session["total_score"] = new_total

        # แก้ไขการส่ง Payload ให้ตรงกับ update_player_data
        updated_data = {
            'total_score': new_total,
            'player_luck': result["next_player_luck"],
            'last_play_date': today_str,
            'free_plays_used': free_plays_used,
            'bought_plays_used': session.get("bought_plays_used", 0)
        }
        update_player_data(sheet_name, row_idx, updated_data)

    # 4. บันทึกประวัติการเล่นลง Database (game.db)
    log_game_play(
        player_id=player_id,
        cards=result["cards"],
        combo_name=result["combo"],
        score_gained=result["score"],
        final_score=result["final_score"]
    )

    return render_template(
        "game.html",
        player_id=player_id,
        player_name=session.get("player_name"),
        cards=result["cards"],
        combo=result["combo"],
        score=result["score"],
        final_score=result["final_score"],
        cost=result["cost"],
        player_luck=result["player_luck"],
        event_luck=result["event_luck"],
        final_luck=result["final_luck"],
        show_luck=SHOW_LUCK_TO_PLAYERS,
        plays_left=DAILY_FREE_LIMIT - free_plays_used
    )


@app.route("/ranking")
def ranking():
    if "player_id" not in session:
        return redirect("/login")

    period = request.args.get("period", "all")
    # แก้ไขการตัด argument period ออก เพื่อให้แมตช์กับ sheets_service
    top_players = get_leaderboard(limit=100)

    return render_template(
        "ranking.html",
        player_id=session.get("player_id"),
        player_name=session.get("player_name"),
        top_players=top_players,
        current_period=period
    )


@app.route("/history")
def history():
    if "player_id" not in session:
        return redirect("/login")

    player_id = session.get("player_id")
    history_logs = get_player_history(player_id, limit=20)

    return render_template(
        "history.html",
        player_id=player_id,
        player_name=session.get("player_name"),
        history_logs=history_logs
    )


@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    global EVENT_LUCK, SHOW_LUCK_TO_PLAYERS

    if "player_id" not in session:
        return redirect("/login")

    current_player_id = session.get("player_id", "").strip().upper()
    if current_player_id not in [aid.upper() for aid in ADMIN_IDS]:
        return redirect("/home")

    msg = None

    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_event":
            try:
                EVENT_LUCK = float(request.form.get("event_luck", 0.0))
                SHOW_LUCK_TO_PLAYERS = "show_luck" in request.form
                msg = "✅ อัปเดตค่า Event สำเร็จ!"
            except ValueError:
                msg = "❌ กรุณากรอกตัวเลขค่า Luck"

        elif action == "modify_score":
            target_id = request.form.get("target_player_id", "").strip()
            try:
                score_change = int(request.form.get("score_change", 0))
                player_info = get_player_data(target_id)
                
                if player_info:
                    new_score = player_info["total_score"] + score_change
                    updated_data = {
                        'total_score': new_score,
                        'player_luck': player_info["player_luck"],
                        'last_play_date': player_info["last_play_date"],
                        'free_plays_used': player_info["free_plays_used"],
                        'bought_plays_used': player_info["bought_plays_used"]
                    }
                    update_player_data(player_info["sheet_name"], player_info["row_idx"], updated_data)
                    msg = f"✅ ปรับคะแนนของ {target_id} ({score_change}) สำเร็จ!"
                else:
                    msg = f"❌ ไม่พบรหัสผู้เล่น {target_id}"
            except ValueError:
                msg = "❌ กรุณากรอกจำนวนคะแนนเป็นตัวเลข"

    return render_template(
        "dashboard.html",
        event_luck=EVENT_LUCK,
        show_luck=SHOW_LUCK_TO_PLAYERS,
        msg=msg
    )


if __name__ == "__main__":
    app.run(debug=True)
