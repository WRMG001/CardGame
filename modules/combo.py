import re

def parse_card(card_str):
    """ แยกแต้มและดอกออกจากไพ่ เช่น '10♠' -> (10, '♠') หรือ 'Joker' """
    if not card_str:
        return 0, ''
    
    card_text = str(card_str).strip()
    
    # กรณีเป็นไพ่ Joker
    if "joker" in card_text.lower() or "🃏" in card_text:
        return 99, 'JOKER'

    # เช็ก Regex โดยวาง '10' ไว้หน้าสุดเพื่อไม่ให้ถูกตัดเป็นเลข '1'
    match = re.match(r'^(10|[2-9]|[JQKAjqka])', card_text)
    if not match:
        return 0, ''
        
    rank_str = match.group(1).upper()
    suit = card_text[len(match.group(1)):].strip()
    
    rank_map = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    rank = rank_map.get(rank_str, 0)
    clean_suit = suit[0] if suit else ''
    
    return rank, clean_suit


def check_combo(cards):
    """ 
    ตรวจสอบคอมโบของไพ่ 3 ใบให้ตรงกับตาราง SCORES ใน modules/score.py 
    """
    if not cards or len(cards) < 3:
        return "High Card"

    parsed = [parse_card(c) for c in cards]
    ranks = sorted([p[0] for p in parsed])
    suits = [p[1] for p in parsed]

    # ถ้ามีไพ่ที่แปลงค่าไม่ได้ ให้ตกเป็น High Card
    if 0 in ranks:
        return "High Card"

    # นับจำนวนไพ่ Joker ในมือ
    joker_count = ranks.count(99)

    # 1. Joker Trio (100 แต้ม): Joker ทั้ง 3 ใบ
    if joker_count == 3:
        return "Joker Trio"

    # 2. Wild Triple 🎰 (30 แต้ม): มี Joker 2 ใบ + ไพ่ธรรมดา 1 ใบ
    if joker_count == 2:
        return "Wild Triple 🎰"

    # 3. Wild Pair 🃏✨ (5 แต้ม): มี Joker 1 ใบ + ไพ่ธรรมดา 2 ใบ
    if joker_count == 1:
        return "Wild Pair 🃏✨"

    # --- กรณีเป็นไพ่ธรรมดา ทั้ง 3 ใบ (ไม่มี Joker) ---

    # เช็ก ดอกเดียวกัน (Flush)
    is_flush = len(set(suits)) == 1 and suits[0] != ''

    # เช็ก เรียงแต้ม (Straight)
    is_straight = (ranks[2] - ranks[1] == 1) and (ranks[1] - ranks[0] == 1)
    # กรณีสเตรทพิเศษ A-2-3
    if ranks == [2, 3, 14]:
        is_straight = True

    # นับจำนวนแต้มซ้ำ
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)

    # 4. Royal Straight Flush (80 แต้ม): Q-K-A ดอกเดียวกัน (ชุดใหญ่สุดของไพ่ 3 ใบ)
    if is_straight and is_flush and ranks == [12, 13, 14]:
        return "Royal Straight Flush"

    # 5. Straight Flush (60 แต้ม): ไพ่เรียงแต้ม + ดอกเดียวกัน
    if is_straight and is_flush:
        return "Straight Flush"

    # 6. Three of a Kind (50 แต้ม): ตองปกติ (แต้มเดียวกัน 3 ใบ)
    if counts == [3]:
        return "Three of a Kind"

    # 7. Straight (25 แต้ม): ไพ่เรียงแต้มกัน 3 ใบ
    if is_straight:
        return "Straight"

    # 8. Flush (20 แต้ม): ไพ่ดอกเดียวกัน 3 ใบ
    if is_flush:
        return "Flush"

    # 9. Royal Combo (15 แต้ม): ไพ่หน้าคนทั้งหมด (J, Q, K, A) 3 ใบ (ไม่เรียง/คนละดอก)
    if all(r >= 11 for r in ranks):
        return "Royal Combo"

    # 10. One Pair (3 แต้ม): คู่ธรรมดา 1 คู่
    if counts == [2, 1]:
        return "One Pair"

    # 11. High Card (0 แต้ม)
    return "High Card"
