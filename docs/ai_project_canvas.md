# AI Project Canvas — Bakery Daily Demand Prediction (P1 / M1)

| องค์ประกอบ | รายละเอียด |
|---|---|
| **Value Proposition** | เจ้าของร้านรู้ล่วงหน้าว่าพรุ่งนี้ควรเตรียมสินค้าแต่ละชนิดเท่าไร → ลดของขาดและของเหลือทิ้ง |
| **Customer / User** | เจ้าของร้าน, พนักงานฝ่ายผลิต (คนอบขนมตอนเช้า) |
| **Prediction Task** | Regression (quantile) — ยอดขายรายสินค้าของวันถัดไป |
| **Decision** | จำนวนที่ควรเตรียม = ceil(F_q) − ของคงเหลือ, q = (ราคา − ต้นทุน)/ราคา |
| **Data Sources** | French Bakery Daily Sales (Kaggle), ปฏิทินวันหยุด |
| **Data Collection / Labels** | label = ยอดขายจริงของวันนั้น (ได้มาฟรีจาก POS ทุกวัน) |
| **Features** | lag 1/7/14, rolling mean/std, วันในสัปดาห์, เดือน, วันหยุด, สินค้า |
| **Offline Metrics** | WAPE, MAE, Pinball loss @ q |
| **Business Metrics** | stockout rate, waste rate, กำไรที่หายไป/วัน |
| **Gating** | ดีกว่า seasonal-naive ≥ 10%, p95 < 200 ms, model < 50 MB |
| **Making Predictions** | Batch ทุกคืน + Real-time API |
| **Live Monitoring** | PSI (data drift), rolling WAPE (concept drift), latency/error |
| **Risks / ผลกระทบเมื่อผิด** | ทำนายต่ำ → ของหมด เสียลูกค้า; ทำนายสูง → ของเหลือทิ้ง ขาดทุน |
| **Cost / Feasibility** | TODO(M1) |

## 5 คำถามตรวจสอบหัวข้อ
1. ทำนายผิดใครเดือดร้อน: TODO
2. ตัวชี้วัดธุรกิจ ↔ ตัวชี้วัดโมเดล: TODO
3. Data / Concept Drift ที่คาดว่าจะเกิด: TODO
4. ต้องตอบเร็วแค่ไหน / ปริมาณคำขอ: TODO
5. โมเดลใหม่แย่กว่าเดิม รู้ได้อย่างไร / ย้อนกลับอย่างไร: TODO
