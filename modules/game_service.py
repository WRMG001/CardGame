import random
import sqlite3
from modules.card_engine import draw_cards
from modules.combo import check_combo
from modules.score import calculate_score
from modules.lucky import update_player_luck

def get_db():
    conn = sqlite3.connect('database/game.db')
    conn.row_factory = sqlite3.Row
    
    try:
        conn.execute("ALTER TABLE players ADD COLUMN last_play_date TEXT;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
        
    return conn

def format_card_to_string(card):
    if isinstance(card, dict):
        rank = card.get("rank", card.get("value", ""))
        suit = card.get("suit", "")
        return f"{rank}{suit}".strip()
    return str(card).strip()

def evaluate_joker_combo(cards):
    joker_cards = [c for c in cards if "Joker" in str(c)]
    joker_count = len(joker_cards)

    if joker_count == 0:
        return None

    if joker_count >= 2:
        return {
            "combo": "Double Joker 🃏🃏",
            "raw_score": 10,
            "play_cost": 0,
            "final_score": 10
        }

    normal_cards = [c for c in cards if "Joker" not in str(c)]
    ranks = [c[:-1] if len(c) > 1 and c[-1] in ['♠', '♥', '♦', '♣'] else c for c in normal_cards]

    if len(ranks) == 2 and ranks[0] == ranks[1]:
        return {
            "combo": "Wild Triple 🎰",
            "raw_score": 8,
            "play_cost": 0,
            "final_score": 8
        }
    
    return {
        "combo": "Wild Pair 🃏✨",
        "raw_score": 5,
        "play_cost": 0,
        "final_score": 5
    }

def play_game(player_id=None, player_luck=0.0, event_luck=0.0, player_score=10):
    if player_id:
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT player_luck, score FROM players WHERE player_id = ?", (player_id,))
            p = cursor.fetchone()
            conn.close()
            if p:
                player_luck = p["player_luck"] if p["player_luck"] is not None else 0.0
                player_score = p["score"] if p["score"] is not None else 10
        except Exception as e:
            print(f"⚠️ Fetch Player Data Error in play_game: {e}")

    final_luck = round(player_luck + event_luck, 2)
    
    try:
        raw_cards = draw_cards(luck=final_luck)
        if isinstance(raw_cards, list):
            cards = [format_card_to_string(c) for c in raw_cards]
        else:
            cards = [format_card_to_string(raw_cards)]
    except Exception as e:
        print(f"⚠️ Card Engine Error: {e}")
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        cards = [f"{random.choice(ranks)}{random.choice(suits)}" for _ in range(3)]

    joker_result = evaluate_joker_combo(cards)

    if joker_result:
        combo_name = joker_result["combo"]
        raw_score = joker_result["raw_score"]
        play_cost = joker_result["play_cost"]
        final_score = joker_result["final_score"]
    else:
        try:
            combo_name = check_combo(cards)
        except Exception as e:
            print(f"⚠️ Combo Check Error: {e}")
            combo_name = "High Card"

        try:
            raw_score, play_cost, final_score, can_play = calculate_score(combo_name, player_score)
        except Exception as e:
            print(f"⚠️ Score Calculate Error: {e}")
            raw_score = 0
            play_cost = 0
            final_score = 0

    try:
        next_luck = update_player_luck(current_luck=player_luck, combo=combo_name, cards=cards)
    except Exception as e:
        print(f"⚠️ Lucky Update Error: {e}")
        next_luck = player_luck

    return {
        "success": True,
        "cards": cards,
        "combo": combo_name,
        "combo_name": combo_name,
        "score_gained": raw_score,
        "score": raw_score,
        "cost": play_cost,
        "final_score": final_score,
        "player_luck": player_luck,
        "event_luck": event_luck,
        "final_luck": final_luck,
        "next_player_luck": next_luck
    }
