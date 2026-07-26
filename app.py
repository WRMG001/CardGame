from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime

from config import SECRET_KEY
from modules.auth import login_player, logout_player
from modules.game_service import play_game
from modules.sheets_service import update_player_data, get_leaderboard, get_player_data, get_all_players
from modules.history import log_game_play, get_player_history

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 1. Admin IDs
ADMIN_IDS = ["ADMIN01", "ADMIN02", "ADMIN03"]

# 2. โควตาเล่นต่อวัน และ ค่าธรรมเนียมกดเล่น
DAILY_PLAY_LIMIT = 3    # เล่นได้สูงสุดวันละ 3 ครั้ง
PLAY_COST_POINTS = 1    # เสีย 1 แต้มทุกครั้งที่กดเล่น

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
        return render_template("login.html", error="ไม่พบ Player ID หรือรูปแบบรหัสไม่ถูกต้อง")
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
    
    # 1. ดึงข้อมูลจำนวนครั้งที่เล่นไปแล้ว
    try:
        player_info = get_player_data(player_id)
        plays_used = int(player_info.get("free_plays_used", 0)) if player_info else int(session.get("free_plays_used", 0))
        total_score = int(player_info.get("total_score", 0)) if player_info else int(session.get("total_score", 0))
    except Exception:
        plays_used = int(session.get("free_plays_used", 0))
        total_score = int(session.get("total_score", 0))

    # 2. เช็กโควตา "ก่อน" เริ่มเล่นเกม ถ้าครบ/เกินแล้ว ให้ส่งไปหน้าสิทธิ์หมดทันที
    if plays_used >= DAILY_PLAY_LIMIT:
        return render_template(
            "game_limit.html",
            player_id=player_id,
            player_name=session.get("player_name", "Player"),
            max_limit=DAILY_PLAY_LIMIT,
            total_score=total_score
        )

    # 3. เล่นเกมและเพิ่มสิทธิ์การเล่น
    player_luck = float(session.get("player_luck", 0.0))
    result = play_game(player_luck=player_luck, event_luck=EVENT_LUCK)

    plays_used += 1
    session["free_plays_used"] = plays_used
    
    new_total = total_score + result["final_score"] - PLAY_COST_POINTS
    session["total_score"] = new_total

    # อัปเดตลง Database / Google Sheet แบบปลอดภัย
    try:
        update_player_data(session.get("sheet_name"), session.get("row_idx"), {
            'total_score': new_total,
            'free_plays_used': plays_used
        })
    except Exception as e:
        print(f"Sheet update error: {e}")

    # คำนวณสิทธิ์ที่เหลืออยู่จริงๆ หลังเล่นรอบนี้
    remaining_plays = max(0, DAILY_PLAY_LIMIT - plays_used)

    return render_template(
        "game.html",
        player_id=player_id,
        player_name=session.get("player_name", "Player"),
        cards=result["cards"],
        combo=result["combo"],
        final_score=result["final_score"],
        total_score=new_total,
        plays_left=remaining_plays
    )

@app.route("/ranking")
def ranking():
    if "player_id" not in session:
        return redirect("/login")

    top_10_players = get_leaderboard(limit=10) # ดึง Top 10
    
    # ดึงรายชื่อผู้เล่นทั้งหมดที่มีสถิติ/กดเล่นแล้ว
    try:
        all_players = get_all_players() # หรือฟังก์ชันดึงผู้เล่นทั้งหมดใน sheets_service
    except Exception:
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
            target_id = request.form.get("target_player_id", "").strip()
            searched_player = get_player_data(target_id)
            if not searched_player:
                msg = f"❌ ไม่พบรหัสผู้เล่น {target_id}"

        elif action == "modify_score":
            target_id = request.form.get("target_player_id", "").strip()
            try:
                score_change = int(request.form.get("score_change", 0))
                player_info = get_player_data(target_id)
                
                if player_info:
                    new_score = player_info.get("total_score", 0) + score_change
                    updated_data = {
                        'total_score': new_score,
                        'player_luck': player_info.get("player_luck", 0.0),
                        'last_play_date': player_info.get("last_play_date", ""),
                        'free_plays_used': player_info.get("free_plays_used", 0)
                    }
                    update_player_data(player_info["sheet_name"], player_info["row_idx"], updated_data)
                    msg = f"✅ ปรับคะแนนของ {target_id} เป็น {new_score} แต้มสำเร็จ!"
                    searched_player = get_player_data(target_id)
                else:
                    msg = f"❌ ไม่พบรหัสผู้เล่น {target_id}"
            except Exception as e:
                msg = f"❌ เกิดข้อผิดพลาด: {str(e)}"

        elif action == "reset_limit":
            target_id = request.form.get("target_player_id", "").strip()
            player_info = get_player_data(target_id)
            if player_info:
                updated_data = {
                    'total_score': player_info.get("total_score", 0),
                    'player_luck': player_info.get("player_luck", 0.0),
                    'last_play_date': player_info.get("last_play_date", ""),
                    'free_plays_used': 0
                }
                update_player_data(player_info["sheet_name"], player_info["row_idx"], updated_data)
                msg = f"✅ รีเซ็ตจำนวนรอบเล่นประจำวันของ {target_id} เรียบร้อย!"
                searched_player = get_player_data(target_id)
            else:
                msg = f"❌ ไม่พบรหัสผู้เล่น {target_id}"

    try:
        return render_template(
            "dashboard.html",
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
