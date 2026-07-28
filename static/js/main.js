// อาร์เรย์สำหรับสุ่มหน้าไพ่หลอกๆ ตอนหมุน
const dummyRanks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', 'Joker'];
const dummySuits = ['♠', '♥', '♦', '♣'];

function getRandomDummyCard() {
    const rank = dummyRanks[Math.floor(Math.random() * dummyRanks.length)];
    if (rank === 'Joker') return 'Joker 🃏';
    const suit = dummySuits[Math.floor(Math.random() * dummySuits.length)];
    return `${rank}${suit}`;
}

async function handleDrawCard() {
    const drawBtn = document.getElementById('drawBtn');
    const resultBox = document.getElementById('resultBox');
    const container = document.getElementById('cardContainer');
    
    // 1. ล็อคปุ่มและเตรียม UI
    drawBtn.disabled = true;
    drawBtn.innerText = "กำลังหมุน... 🎰";
    resultBox.innerHTML = '<h3>กำลังลุ้นไพ่...</h3><p>ขอให้โชคดี!</p>';

    // สร้างกล่องไพ่ 3 ใบรอไว้เลย
    container.innerHTML = `
        <div class="card card-front" id="slot-0">❓</div>
        <div class="card card-front" id="slot-1">❓</div>
        <div class="card card-front" id="slot-2">❓</div>
    `;

    const slots = [
        document.getElementById('slot-0'),
        document.getElementById('slot-1'),
        document.getElementById('slot-2')
    ];

    // 2. เริ่มแอนิเมชันสล็อตหมุนติ้วๆ (เปลี่ยนหน้าไพ่ทุกๆ 50 มิลลิวินาที)
    let spinInterval = setInterval(() => {
        slots.forEach(slot => {
            slot.innerText = getRandomDummyCard();
        });
    }, 50);

    try {
        // 3. ยิงไปขอผลลัพธ์จริงจาก Backend
        const response = await fetch('/api/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ player_id: CURRENT_PLAYER_ID })
        });
        const data = await response.json();

        // หน่วงเวลาเพิ่มความลุ้นอีกสัก 1.5 วินาที (เพื่อให้คนเล่นได้เห็นมันหมุน)
        await new Promise(resolve => setTimeout(resolve, 1500));

        if (data.success) {
            // 4. ค่อยๆ หยุดไพ่ทีละใบ (ดึงอารมณ์สล็อต)
            clearInterval(spinInterval); // หยุดหมุนรวม
            
            // ใบที่ 1 หยุดทันที
            slots[0].innerText = data.cards[0];
            slots[0].classList.add('stop-spin');
            
            // ใบที่ 2 หยุดหลังจาก 0.5 วิ
            setTimeout(() => {
                slots[1].innerText = data.cards[1];
                slots[1].classList.add('stop-spin');
            }, 500);

            // ใบที่ 3 (ใบสุดท้าย) หยุดหลังจาก 1 วิ พร้อมโชว์ผลลัพธ์
            setTimeout(() => {
                slots[2].innerText = data.cards[2];
                slots[2].classList.add('stop-spin');
                
                // แสดงคอมโบและคะแนน
                resultBox.innerHTML = `
                    <h3 class="combo-highlight">ผลลัพธ์: ${data.combo}</h3>
                    <p>คุณได้รับคะแนนเพิ่ม: <strong>+${data.score_gained}</strong> แต้ม</p>
                `;
                drawBtn.innerText = "🎲 สุ่มอีกครั้ง";
                drawBtn.disabled = false;
            }, 1200); // ใบสุดท้ายหน่วงนานหน่อยให้ลุ้นใจขาด

        } else {
            // กรณีสิทธิ์หมด (เคลียร์หน้าหมุนออก)
            clearInterval(spinInterval);
            resultBox.innerHTML = `<p class="error-text">⚠️ ${data.message}</p>`;
            drawBtn.innerText = "สิทธิ์การเล่นวันนี้หมดแล้ว";
            slots.forEach(slot => slot.innerText = "❌");
        }
    } catch (error) {
        clearInterval(spinInterval);
        console.error("Error:", error);
        resultBox.innerHTML = `<p class="error-text">⚠️ เกิดข้อผิดพลาดในการเชื่อมต่อ</p>`;
        drawBtn.innerText = "ลองใหม่อีกครั้ง";
        drawBtn.disabled = false;
    }
}
