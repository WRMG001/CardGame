from flask import Flask, render_template, request, redirect, session, url_for
from datetime import datetime

from config import SECRET_KEY
from modules.auth import login_player, logout_player
from modules.game_service import play_game
from modules.sheets_service import update_player_data, get_leaderboard, get_player_data
from modules.history import log_game_play, get_player_history

app = Flask(__name__)
app.secret_key = SECRET_KEY

# 1. Admin IDs
ADMIN_IDS = ["ADMIN01", "ADMIN02", "ADMIN03"]

# 2. สิทธิ์เล่นฟรีรายวันตาม Role (3 ครั้ง/วัน เท่ากันหมด)
ROLE_DAILY_LIMITS = {
    'admin': 999,
    'customer': 3,
    'host': 3,
    'black': 3,
    'bartender': 3,
    'waiter': 3,
    'security': 3,
}
DEFAULT_DAILY_LIMIT = 3

# 3. เงื่อนไขการซื้อสิทธิ์เพิ่ม
DAILY_BUY_LIMIT = 2     # ซื้อเพิ่มได้สูงสุด 2 ครั้ง/วัน
BUY_COST_POINTS = 2     # จ่ายครั้งละ 2 แต้ม

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
    user_role = str(session.get("role", "customer")).lower()
    
    daily_free_limit = ROLE_DAILY_LIMITS.get(user_role, DEFAULT_DAILY_LIMIT)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    last_play_date = session.get("last_play_date", "")
    free_plays_used = session.get("free_plays_used", 0)
    bought_plays = session.get("bought_plays", 0)           # สิทธิ์ที่ซื้อเพิ่มไปแล้วในวันนี้
    bought_plays_used = session.get("bought_plays_used", 0) # สิทธิ์ซื้อที่ใช้ไปแล้ว

    # 🛑 รีเซ็ตทุกอย่างเมื่อขึ้นวันใหม่ (ไม่สะสมสิทธิ์)
    if last_play_date != today_str:
        free_plays_used = 0
        bought_plays = 0
        bought_plays_used = 0
        session["last_play_date"] = today_str
        session["free_plays_used"] = 0
        session["bought_plays"] = 0
        session["bought_plays_used"] = 0

    free_left = max(0, daily_free_limit - free_plays_used)
    bought_left = max(0, bought_plays - bought_plays_used)

    # 🛑 เช็กว่าหมดสิทธิ์เล่นทั้งฟรีและที่ซื้อมาหรือยัง
    if free_left <= 0 and bought_left <= 0:
        return render_template(
            "game_limit.html",
            player_id=player_id,
            player_name=session.get("player_name"),
            max_limit=daily_free_limit,
            can_buy=(bought_plays < DAILY_BUY_LIMIT), # บอก UI ว่ายังซื้อเพิ่มได้ไหม
            buy_cost=BUY_COST_POINTS,
            total_score=session.get("total_score", 0)
        )

    # เล่นเกมสุ่มไพ่
    player_luck = session.get("player_luck", 0.0)
    result = play_game(player_luck=player_luck, event_luck=EVENT_LUCK)

    # ตัดสิทธิ์ (ใช้สิทธิ์ฟรีก่อน ถ้าหมดค่อยหักสิทธิ์ซื้อ)
    if free_left > 0:
        free_plays_used += 1
        session["free_plays_used"] = free_plays_used
    else:
        bought_plays_used += 1
        session["bought_plays_used"] = bought_plays_used

    session["player_luck"] = result["next_player_luck"]

    # อัปเดต Google Sheet
    sheet_name = session.get("sheet_name")
    row_idx = session.get("row_idx")

    if sheet_name and row_idx:
        current_total = session.get("total_score", 0)
        new_total = current_total + result["final_score"]
        session["total_score"] = new_total

        updated_data = {
            'total_score': new_total,
            'player_luck': result["next_player_luck"],
            'last_play_date': today_str,
            'free_plays_used': free_plays_used,
            'bought_plays': bought_plays,
            'bought_plays_used': bought_plays_used
        }
        update_player_data(sheet_name, row_idx, updated_data)

    # บันทึก History
    log_game_play(
        player_id=player_id,
        cards=result["cards"],
        combo_name=result["combo"],
        score_gained=result["score"],
        final_score=result["final_score"]
    )

    total_plays_left = (daily_free_limit - free_plays_used) + (bought_plays - bought_plays_used)

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
        plays_left=total_plays_left
    )


@app.route("/buy_play", methods=["POST"])
def buy_play():
    """Route สำหรับหัก 2 แต้ม เพื่อซื้อสิทธิ์เล่นเพิ่ม 1 ครั้ง (จำกัดไม่เกิน 2 ครั้ง/วัน)"""
    if "player_id" not in session:
        return redirect("/login")

    today_str = datetime.now().strftime("%Y-%m-%d")
    last_play_date = session.get("last_play_date", "")
    
    if last_play_date != today_str:
        session["free_plays_used"] = 0
        session["bought_plays"] = 0
        session["bought_plays_used"] = 0
        session["last_play_date"] = today_str

    bought_plays = session.get("bought_plays", 0)
    current_score = session.get("total_score", 0)

    # เช็กเงื่อนไข: ยังซื้อไม่เกิน 2 ครั้ง และมีคะแนนพอจ่าย 2 แต้ม
    if bought_plays < DAILY_BUY_LIMIT and current_score >= BUY_COST_POINTS:
        # หักคะแนน 2 แต้ม
        new_score = current_score - BUY_COST_POINTS
        bought_plays += 1

        session["total_score"] = new_score
        session["bought_plays"] = bought_plays

        # อัปเดตข้อมูลลง Google Sheet
        sheet_name = session.get("sheet_name")
        row_idx = session.get("row_idx")
        if sheet_name and row_idx:
            updated_data = {
                'total_score': new_score,
                'player_luck': session.get("player_luck", 0.0),
                'last_play_date': today_str,
                'free_plays_used': session.get("free_plays_used", 0),
                'bought_plays': bought_plays,
                'bought_plays_used': session.get("bought_plays_used", 0)
            }
            update_player_data(sheet_name, row_idx, updated_data)

        return redirect("/game")

    return redirect("/game")


@app.route("/ranking")
def ranking():
    if "player_id" not in session:
        return redirect("/login")

    period = request.args.get("period", "all")
    top_players = get_leaderboard(limit=10) # ล็อกไว้เฉพาะ Top 10

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
                        'bought_plays': player_info.get("bought_plays", 0),
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
