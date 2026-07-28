document.addEventListener("DOMContentLoaded", () => {
    const playBtn = document.getElementById("playBtn");
    const resultBox = document.getElementById("resultBox");
    const remainingSpinsText = document.getElementById("remainingSpins");

    if (!playBtn) return;

    playBtn.addEventListener("click", async () => {
        // 1. ปิดการใช้งานปุ่มชั่วคราว
        playBtn.disabled = true;
        playBtn.innerText = "⏳ กำลังหมุน...";
        resultBox.innerHTML = `<h3>กำลังลุ้นไพ่...</h3><p>ขอให้โชคดี!</p>`;

        // 2. ซ่อนหน้าไพ่เดิม และเตรียมเล่นอนิเมชัน
        const cards = document.querySelectorAll(".card-container");
        cards.forEach(card => card.classList.remove("flipped"));

        try {
            // 3. ยิง API ไปสุ่มไพ่ หักสิทธิ์การเล่น และบันทึกลง Google Sheets ที่ฝั่ง app.py
            const response = await fetch("/api/play", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                alert(data.message || "เกิดข้อผิดพลาดในการสุ่มไพ่");
                playBtn.disabled = false;
                playBtn.innerText = "🎰 เปิดไพ่อีกรอบ";
                return;
            }

            // 4. แสดงอนิเมชันลุ้นไพ่ (รอประมาณ 1.5 วินาที)
            setTimeout(() => {
                // อัปเดตหน้าไพ่ด้วยข้อมูลที่ส่งมาจาก Server
                data.cards.forEach((cardData, index) => {
                    const frontCard = document.getElementById(`card-front-${index}`);
                    if (frontCard) {
                        frontCard.innerHTML = renderCardHTML(cardData);
                    }
                    // พลิกไพ่เปิดขึ้นมา
                    if (cards[index]) {
                        cards[index].classList.add("flipped");
                    }
                });

                // 5. แสดงผลลัพธ์ แต้มที่ได้ และคอมโบ
                resultBox.innerHTML = `
                    <h3 style="color: #00f2fe;">🎉 Combo: ${data.combo_name}</h3>
                    <p style="font-size: 18px;">คะแนนที่ได้: <strong style="color: #ffb703;">+${data.score}</strong></p>
                `;

                // 6. อัปเดตสิทธิ์คงเหลือบนหน้าจอทันที
                if (remainingSpinsText && data.remaining_spins !== undefined) {
                    remainingSpinsText.innerText = data.remaining_spins;
                }

                // 7. จัดการสถานะปุ่ม
                if (data.remaining_spins <= 0) {
                    playBtn.disabled = true;
                    playBtn.innerText = "❌ สิทธิ์หมดแล้ว";
                } else {
                    playBtn.disabled = false;
                    playBtn.innerText = "🔄 เปิดไพ่อีกรอบ";
                }

            }, 1500);

        } catch (error) {
            console.error("Error:", error);
            alert("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้");
            playBtn.disabled = false;
            playBtn.innerText = "🔄 ลองใหม่อีกครั้ง";
        }
    });
});

// ฟังก์ชันช่วยเรนเดอร์สัญลักษณ์ไพ่
function renderCardHTML(card) {
    const isRed = card.suit === '♥' || card.suit === '♦';
    const colorStyle = isRed ? 'color: #e63946;' : 'color: #1d3557;';
    return `
        <div style="font-weight: bold; font-size: 16px; ${colorStyle} align-self: flex-start;">${card.value}<br>${card.suit}</div>
        <div style="font-size: 28px; ${colorStyle}">${card.suit}</div>
        <div style="font-weight: bold; font-size: 16px; ${colorStyle} align-self: flex-end; transform: rotate(180deg);">${card.value}<br>${card.suit}</div>
    `;
}
