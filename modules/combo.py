import re

def parse_card(card_str):
    """ แยกแต้มและดอกออกจากไพ่ เช่น '10♠' -> (10, '♠') """
    if not card_str:
        return 0, ''
    
    card_text = str(card_str).strip()
    
    # แก้ไข Regex ให้เช็ก '10' ก่อนกลุ่มตัวเลขเดี่ยว เพื่อป้องกันไม่ให้ถูกจับเป็นเลข '1'
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
    
    # คืนค่าดอกไพ่ (รองรับ Emoji สัญลักษณ์ดอกไพ่)
    clean_suit = suit[0] if suit else ''
    return rank, clean_suit

def check_combo(cards):
    """ ตรวจสอบคอมโบของไพ่ 3 ใบ """
    if not cards or len(cards) < 3:
        return "High Card"

    parsed = [parse_card(c) for c in cards]
    ranks = sorted([p[0] for p in parsed])
    suits = [p[1] for p in parsed]

    # ถ้ามีไพ่ใบไหนแกะค่าไม่ได้
    if 0 in ranks:
        return "High Card"

    is_flush = len(set(suits)) == 1 and suits[0] != ''
    is_straight = (ranks[2] - ranks[1] == 1) and (ranks[1] - ranks[0] == 1)
    
    # กรณีสเตรทพิเศษ A-2-3
    if ranks == [2, 3, 14]:
        is_straight = True

    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    
    counts = sorted(rank_counts.values(), reverse=True)

    # 1. เช็ก Royal Straight Flush (เรียงดอกเดียวกัน และไพ่สูงสุดคือ A เช่น Q-K-A หรือ J-Q-K / 10-J-Q-K-A)
    if is_straight and is_flush and ranks[2] == 14 and ranks[1] == 13:
        return "Royal Straight Flush"
    # 2. Straight Flush
    elif is_straight and is_flush:
        return "Straight Flush"
    # 3. Three of a Kind (ตอง)
    elif counts == [3]:
        return "Three of a Kind"
    # 4. Straight (เรียง)
    elif is_straight:
        return "Straight"
    # 5. Flush (สี/ดอกเดียวกัน)
    elif is_flush:
        return "Flush"
    # 6. One Pair (คู่)
    elif counts == [2, 1]:
        return "One Pair"
    else:
        return "High Card"
