import random

def create_deck(include_joker=True):
    """ สร้างสำรับไพ่ 52 ใบมาตรฐาน + Joker """
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    deck = [f"{r}{s}" for s in suits for r in ranks]
    
    # เพิ่ม Joker 2 ใบลงในสำรับ (ถ้ากำหนดให้มี)
    if include_joker:
        deck.extend(['🃏Joker1', '🃏Joker2', '🃏Joker3'])
        
    return deck

def draw_cards(luck=0.0, num_cards=3):
    """
    สุ่มดึงไพ่แบบไม่ซ้ำใบใน 1 มือ (Without Replacement)
    """
    deck = create_deck(include_joker=True)
    
    # สุ่มเลือกไพ่ไม่ซ้ำใบ
    drawn_cards = random.sample(deck, num_cards)
    return drawn_cards
