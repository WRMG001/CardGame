import re

def parse_card(card_str):
    """ แยกแต้มและดอกออกจากไพ่ เช่น '10♠' -> (10, '♠') """
    if not card_str:
        return 0, ''
    
    # ใช้ Regex ดึงเฉพาะตัวเลขหรืออักษร J, Q, K, A ออกมาเป็น Rank
    match = re.match(r'^([2-9]|10|[JQKAjqka])', str(card_str).strip())
    if not match:
        return 0, ''
        
    rank_str = match.group(1).upper()
    suit = card_str.replace(match.group(1), '').strip()
    
    rank_map = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    rank = rank_map.get(rank_str, 0)
    
    # คืนค่าดอกไพ่โดยตัด Emoji Variation ออก
    clean_suit = suit[0] if suit else ''
    return rank, clean_suit

def check_combo(cards):
    """ ตรวจสอบคอมโบของไพ่ 3 ใบ """
    if not cards or len(cards) < 3:
        return "High Card"

    parsed = [parse_card(c) for c in cards]
    ranks = sorted([p[0] for p in parsed])
    suits = [p[1] for p in parsed]

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

    if is_straight and is_flush:
        return "Straight Flush"
    elif counts == [3]:
        return "Three of a Kind"
    elif is_straight:
        return "Straight"
    elif is_flush:
        return "Flush"
    elif counts == [2, 1]:
        return "One Pair"
    else:
        return "High Card"