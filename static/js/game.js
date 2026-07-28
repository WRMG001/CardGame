// ฟังก์ชันสุ่มไพ่สไตล์ Slot Machine แบบ 3D
async function startSpin() {
    const btnPlay = document.getElementById('btn-play');
    const cards = document.querySelectorAll('.card-item');
    const comboDisplay = document.getElementById('combo-display');
    const scoreDisplay = document.getElementById('score-display');
    const totalScoreDisplay = document.getElementById('total-score-display');
    const playsLeftDisplay = document.getElementById('plays-left-display');

    // 1. ล็อกปุ่มและเปลี่ยนข้อความระหว่างหมุน
    btnPlay.disabled = true;
    btnPlay.innerText = 'กำลังหมุน...';

    // 2. เริ่มอนิเมชันหมุนไพ่แบบสล็อตสลับไปมา (ลบลายไพ่เก่าออกชั่วคราว)
    cards.forEach(card => {
        card.className = 'card-item spinning';
        card.innerHTML = '<div class="card-back">♦</div>'; // แสดงหลังไพ่ตอนกำลังสุ่ม
    });

    try {
        // 3. ยิง API ไปที่ Backend (/api/play)
        const res = await fetch('/api/play', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await res.json();

        if (!data.success) {
            alert(data.message || 'ไม่สามารถเปิดไพ่ได้');
            cards.forEach(card => card.classList.remove('spinning'));
            btnPlay.disabled = false;
            btnPlay.innerText = 'เปิดไพ่อีกรอบ';
            return;
        }

        // 4. หน่วงเวลาจำลองการหมุน Slot Machine (1.2 วินาที) ก่อนทยอยเฉลยทีละใบ
        setTimeout(() => {
            cards.forEach((card, idx) => {
                // เฉลยหน้าไพ่ไล่ระดับห่างกันใบละ 0.25 วินาที
                setTimeout(() => {
                    card.classList.remove('spinning');
                    card.classList.add('reveal');
                    
                    // แปลงค่า String ของไพ่ (เช่น 8♥, Q♣) ให้เป็น HTML ไพ่จริง
                    card.innerHTML = renderCardUI(data.cards[idx]);
                }, idx * 250);
            });

            // 5. อัปเดตข้อมูลคะแนน คอมโบ และสิทธิ์คงเหลือบน UI หลังไพ่เปิดครบแล้ว
            setTimeout(() => {
                if (comboDisplay) comboDisplay.innerText = `🎉 Combo: ${data.combo}`;
                if (scoreDisplay) scoreDisplay.innerText = `คะแนนที่ได้: +${data.score_gained}`;
                if (totalScoreDisplay) totalScoreDisplay.innerText = data.total_score;
                if (playsLeftDisplay) playsLeftDisplay.innerText = data.plays_left;

                // ตรวจสอบสิทธิ์คงเหลือ หากหมดแล้วให้ล็อกปุ่มทันที
                if (data.plays_left <= 0) {
                    btnPlay.disabled = true;
                    btnPlay.innerText = 'สิทธิ์วันนี้หมดแล้ว';
                } else {
                    btnPlay.disabled = false;
                    btnPlay.innerText = 'เปิดไพ่อีกรอบ';
                }
            }, 800);

        }, 1200);

    } catch (err) {
        console.error('Error playing game:', err);
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์');
        cards.forEach(card => card.classList.remove('spinning'));
        btnPlay.disabled = false;
        btnPlay.innerText = 'เปิดไพ่อีกรอบ';
    }
}

// ฟังก์ชันวาดลายไพ่ให้ตรงตามสัญลักษณ์ และกำหนดสีแดง/ดำ
function renderCardUI(cardStr) {
    if (!cardStr) return '';
    
    // จัดการกรณีเป็นไพ่ Joker
    if (cardStr.includes('Joker')) {
        return `
            <div class="card-face red">
                <div class="card-corner top">🃏</div>
                <div class="card-center">JOKER</div>
                <div class="card-corner bottom">🃏</div>
            </div>`;
    }

    const suit = cardStr.slice(-1); // ดึงดอกไพ่ ♠, ♥, ♦, ♣
    const rank = cardStr.slice(0, -1); // ดึงตัวเลข/อักขระ Q, K, A, 10
    const isRed = (suit === '♥' || suit === '♦') ? 'red' : 'black';

    return `
        <div class="card-face ${isRed}">
            <div class="card-corner top">
                <span>${rank}</span>
                <span>${suit}</span>
            </div>
            <div class="card-center">${suit}</div>
            <div class="card-corner bottom">
                <span>${rank}</span>
                <span>${suit}</span>
            </div>
        </div>
    `;
}