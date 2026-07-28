document.addEventListener("DOMContentLoaded", () => {
    const playBtn = document.getElementById("playBtn");
    const resultBox = document.getElementById("resultBox");
    const remainingSpinsText = document.getElementById("remainingSpins");

    if (!playBtn) return;

    playBtn.addEventListener("click", async () => {
        playBtn.disabled = true;
        playBtn.innerText = "⏳ กำลังหมุน...";
        if (resultBox) {
            resultBox.innerHTML = `<h3>กำลังลุ้นไพ่...</h3><p>ขอให้โชคดี!</p>`;
        }

        const cards = document.querySelectorAll(".card-container");
        cards.forEach(card => card.classList.remove("flipped"));

        try {
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

            setTimeout(() => {
                data.cards.forEach((cardData, index) => {
                    const frontCard = document.getElementById(`card-front-${index}`);
                    if (frontCard) {
                        frontCard.innerHTML = renderCardHTML(cardData);
                    }
                    if (cards[index]) {
                        cards[index].classList.add("flipped");
                    }
                });

                if (resultBox) {
                    const combo = data.combo_name || data.combo || "High Card";
                    const scoreGained = data.score !== undefined ? data.score : data.score_gained;
                    resultBox.innerHTML = `
                        <h3 style="color: #00f2fe;">🎉 Combo: ${combo}</h3>
                        <p style="font-size: 18px;">คะแนนที่ได้: <strong style="color: #ffb703;">+${scoreGained}</strong></p>
                    `;
                }

                const currentSpins = data.remaining_spins !== undefined ? data.remaining_spins : data.plays_left;
                if (remainingSpinsText && currentSpins !== undefined) {
                    remainingSpinsText.innerText = currentSpins;
                }

                if (currentSpins <= 0) {
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

function renderCardHTML(card) {
    let value = "";
    let suit = "";

    if (typeof card === 'object' && card !== null) {
        value = card.value || card.rank || "";
        suit = card.suit || "";
    } else if (typeof card === 'string') {
        const str = card.trim();
        const lastChar = str.slice(-1);
        if (['♠', '♥', '♦', '♣'].includes(lastChar)) {
            suit = lastChar;
            value = str.slice(0, -1);
        } else {
            value = str;
        }
    }

    const isRed = suit === '♥' || suit === '♦';
    const colorStyle = isRed ? 'color: #e63946;' : 'color: #1d3557;';
    
    return `
        <div style="font-weight: bold; font-size: 16px; ${colorStyle} align-self: flex-start;">${value}<br>${suit}</div>
        <div style="font-size: 28px; ${colorStyle}">${suit || value}</div>
        <div style="font-weight: bold; font-size: 16px; ${colorStyle} align-self: flex-end; transform: rotate(180deg);">${value}<br>${suit}</div>
    `;
}
