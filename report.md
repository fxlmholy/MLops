# รายงานโครงงาน CP413008 — Bakery Daily Demand Prediction

> **กฎ:** แต่ละขั้นเขียนเฉพาะ section ของตัวเอง ภายใน PR ของขั้นนั้น (ดู CLAUDE.md §1 และ §7)
> สถานะ: ⬜ ยังไม่เริ่ม · 🟨 กำลังทำ · ✅ เสร็จ

| § | ขั้น | ผู้รับผิดชอบ | สถานะ |
|---|---|---|---|
| 0 | สมาชิกและการแบ่งงาน | M1 + ทุกคน | ⬜ |
| 1 | Problem Framing & AI Project Canvas | M1 | ✅ |
| 2 | Data Ingestion, Split & Validation | M2 | ⬜ |
| 3 | Feature Engineering | M3 | ⬜ |
| 4 | Model Development & Experiment Tracking | M3 | ⬜ |
| 5 | Model Registry, Gate & Rollback | M4 | ⬜ |
| 6 | Serving, Infrastructure & Load Test | M4 | ⬜ |
| 7 | Monitoring, Drift & Retraining | M5 | ⬜ |
| 8 | Pipeline DAG | M2 | ⬜ |
| 9 | CI/CD | M5 | ⬜ |
| 10 | Architecture, Reproducibility & สรุป | M1 | ⬜ |
| 11 | สรุปการใช้ AI (รวมจากทุก section) | M1 | ⬜ |

---

## §0 สมาชิกและการแบ่งงาน
<!-- P0: ทุกคนเพิ่มแถวของตัวเองผ่าน PR ของตัวเอง -->

| รหัส | ชื่อ-สกุล | รหัสนักศึกษา | GitHub | บทบาท |
|---|---|---|---|---|
| M1 | | | | Project Lead / Framing / Report |
| M2 | | | | Data Engineer |
| M3 | | | | ML Engineer |
| M4 | | | | Serving Engineer |
| M5 | | | | Ops Engineer |

---

## §1 Problem Framing & AI Project Canvas
**ผู้รับผิดชอบ:** M1 (@nattapongsric-collab) · **Reviewer:** M5 (@thanachotkam-hue) · **PR:** # · **วันที่เสร็จ:** 2026-10-04

### สิ่งที่ทำ
- เขียน AI Project Canvas ครบทุกช่อง → [`docs/ai_project_canvas.md`](docs/ai_project_canvas.md)
- ตอบ 5 คำถามตรวจสอบหัวข้อ (ใครเดือดร้อน / business metric / drift / latency / rollback) และเหตุผลที่ใช้ ML แทน rule (ใน canvas)
- กำหนด metrics, gating และ SLO ใน [`configs/config.yaml`](configs/config.yaml) (หัวข้อ `metrics`, `gate`, `slo`)

**โจทย์:** พยากรณ์ยอดขายรายสินค้าของวันพรุ่งนี้ (p50 และ p_q) แล้วแนะนำจำนวนที่ควรเตรียม ให้ร้านเบเกอรี่ลดทั้งของขาดและของเหลือทิ้ง

### การตัดสินใจและเหตุผล
- **Quantile regression แทนการทำนายค่าเฉลี่ย** — ความเสียหายของการเตรียมขาดกับเตรียมเกินไม่เท่ากัน จึงทำนาย quantile q = (ราคา − ต้นทุน)/ราคา ตามหลัก newsvendor ซึ่งให้จำนวนเตรียมที่คาดว่ากำไรสูงสุด
- **WAPE เป็น optimizing metric** (เทียบกับ MAPE/RMSE) — WAPE = Σ|y−ŷ| / Σy อ่านเป็น % ได้ง่ายสำหรับเจ้าของร้าน และไม่หารด้วยศูนย์ในวันที่บางสินค้าขายได้ 0 ชิ้น ซึ่ง MAPE ใช้ไม่ได้ ส่วน RMSE ถูกดึงด้วยสินค้าขายดีมากเกินไป
- **Pinball loss @ q เป็น metric รอง** — วัดคุณภาพของ quantile ที่ใช้ตัดสินใจจริง
- **Baseline = seasonal-naive (lag 7)** — คือวิธีที่ร้านใช้อยู่จริง ("เท่าวันเดียวกันสัปดาห์ก่อน") ถ้า ML ชนะไม่ถึง 10% ไม่คุ้มที่จะดูแลระบบที่ซับซ้อนกว่า
- **Serving แบบ Batch + Real-time** — batch ทุกคืนให้ทันก่อนอบตอนเช้า (deadline 06:00) และ API สำหรับถามรายสินค้าระหว่างวัน

| ประเภท | ตัวชี้วัด | เกณฑ์ | อยู่ใน config |
|---|---|---|---|
| Optimizing | WAPE | ต่ำสุด | `metrics.optimizing` |
| Secondary | Pinball loss @ q, MAE | รายงาน | `metrics.secondary` |
| Gating | WAPE ดีกว่า seasonal-naive | ≥ 10% | `gate.min_improvement_vs_naive` |
| Gating | ขนาดโมเดล | < 50 MB | `gate.max_model_size_mb` |
| Gating | p95 latency | < 200 ms | `gate.max_p95_latency_ms` |
| Gating | ข้อมูลผ่าน schema | ต้องผ่าน | `gate.require_schema_pass` |
| Business | stockout rate, waste rate, lost profit/วัน | simulate บน test set (P3) | `metrics.business` |
| SLO | availability / p95 / error rate | ≥ 99% / < 200 ms / < 1% | `slo.*` |
| SLO | batch เสร็จก่อน | 06:00 | `slo.batch_deadline` |

### ผลลัพธ์ / หลักฐาน
- Canvas ครบทุกช่อง ไม่มี TODO เหลือ: `docs/ai_project_canvas.md`
- ค่า metric/gate/SLO ทั้งหมดอยู่ใน `configs/config.yaml` ที่เดียว ให้ `evaluate_gate.py` (M4) และ monitoring (M5) อ่านใช้
- ตัวเลขผลจริง (WAPE ของ baseline เทียบโมเดล และ business metrics) จะมาจากการทดลองใน §3–§4 (M3)

### ปัญหาที่เจอและวิธีแก้
- ขนมปังสดขายข้ามวันไม่ได้ ถ้าใช้ค่าเฉลี่ยจะเตรียมขาดประมาณครึ่งหนึ่งของวัน → แก้ด้วยการทำนาย quantile และคำนวณจำนวนเตรียมแบบ newsvendor
- เพิ่ม key ใหม่ใน `config.yaml` โดย **ไม่แก้ key เดิม** ที่โมดูลของคนอื่นใช้อยู่ (`gate.min_improvement_vs_naive`, `gate.max_model_size_mb`, `slo.*`) เพื่อไม่ให้โค้ดของสมาชิกคนอื่นพัง

### การใช้ AI
- ใช้ Claude Code ช่วยร่างคำตอบ 5 คำถาม, เหตุผลการเลือก metric และจัดรูปแบบตาราง; ตรวจสอบโดย M1 อ่านทุกข้อให้ตรงกับโจทย์และ CLAUDE.md §5 (P1) และเทียบค่าใน config กับเกณฑ์ที่ทีมตกลง

### วิธีรัน/ทดสอบส่วนนี้
```bash
# ตรวจว่า config โหลดได้และมีค่าของ P1
python -c "from src.config import load_config as l; c=l(); print(c['metrics'], c['gate'], c['slo'])"
pytest -q tests/test_smoke.py
```

---

## §2 Data Ingestion, Split & Validation
**ผู้รับผิดชอบ:** M2 · **Reviewer:** M1 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §3 Feature Engineering
**ผู้รับผิดชอบ:** M3 · **Reviewer:** M2 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §4 Model Development & Experiment Tracking
**ผู้รับผิดชอบ:** M3 · **Reviewer:** M2 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
| Run | โมเดล | Hyperparams | WAPE | MAE | Pinball@q | Stockout | Waste | ผ่าน Gate? |
|---|---|---|---|---|---|---|---|---|
| 1 | Seasonal-naive | – | | | | | | |
| 2 | Linear Regression | | | | | | | |
| 3 | LightGBM default | | | | | | | |
| 4 | LightGBM tuned | | | | | | | |

### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §5 Model Registry, Gate & Rollback
**ผู้รับผิดชอบ:** M4 · **Reviewer:** M3 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §6 Serving, Infrastructure & Load Test
**ผู้รับผิดชอบ:** M4 · **Reviewer:** M3 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
| Metric | SLO | วัดได้ | ผ่าน? |
|---|---|---|---|
| p50 latency | – | | |
| p95 latency | < 200 ms | | |
| Throughput (RPS) | – | | |
| Error rate | < 1% | | |

### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §7 Monitoring, Drift & Retraining
**ผู้รับผิดชอบ:** M5 · **Reviewer:** M4 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
| Alert | เกณฑ์ | ผลจากการจำลอง |
|---|---|---|
| Data Drift | PSI > 0.2 | |
| Concept Drift | WAPE_7d > 1.2 × baseline | |
| Latency | p95 > 200 ms | |
| Error rate | > 1% | |

### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §8 Pipeline DAG
**ผู้รับผิดชอบ:** M2 · **Reviewer:** M1 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §9 CI/CD
**ผู้รับผิดชอบ:** M5 · **Reviewer:** M4 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน (ต้องมีทั้ง PASS และ FAIL)
### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

---

## §10 Architecture, Reproducibility & สรุป
**ผู้รับผิดชอบ:** M1 · **Reviewer:** M5 · **PR:** # · **วันที่เสร็จ:**

### แผนภาพสถาปัตยกรรม
### ผลทดสอบรันจากเครื่องเปล่า
### สรุปผลเชิงธุรกิจ
### ข้อจำกัดและงานในอนาคต

---

## §11 สรุปการใช้ AI
| ส่วนของงาน | เครื่องมือ AI | ใช้ช่วยทำอะไร | ผู้ตรวจสอบ/อธิบายได้ |
|---|---|---|---|
| | | | |
