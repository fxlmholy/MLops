# รายงานโครงงาน CP413008 — Bakery Daily Demand Prediction

> **กฎ:** แต่ละขั้นเขียนเฉพาะ section ของตัวเอง ภายใน PR ของขั้นนั้น (ดู CLAUDE.md §1 และ §7)
> สถานะ: ⬜ ยังไม่เริ่ม · 🟨 กำลังทำ · ✅ เสร็จ

| § | ขั้น | ผู้รับผิดชอบ | สถานะ |
|---|---|---|---|
| 0 | สมาชิกและการแบ่งงาน | M1 + ทุกคน | ⬜ |
| 1 | Problem Framing & AI Project Canvas | M1 | ✅ |
| 2 | Data Ingestion, Split & Validation | M2 | ✅ |
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
| M1 | | 67xxxxxxxx | @nattapongsric-collab | Project Lead / Framing / Report |
| M2 | | 67xxxxxxxx | NongPP235 | Data Engineer |
| M3 | | | | ML Engineer |
| M4 | | | @fxlmholy | Serving Engineer |
| M5 | ธนโชติ กมลเลิศ|673380630-1 |thanachotkam-hue | Ops Engineer |

---

## §1 Problem Framing & AI Project Canvas
**ผู้รับผิดชอบ:** M1 (@nattapongsric-collab) · **Reviewer:** M5 (@thanachotkam-hue) · **PR:** #2 · **วันที่เสร็จ:** 2026-10-04

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
**ผู้รับผิดชอบ:** M2 (@NongPP235) · **Reviewer:** M1 (@nattapongsric-collab) · **PR:** #6 · **วันที่เสร็จ:** 2026-10-04

### สิ่งที่ทำ
- `src/ingest.py` — อ่าน csv ดิบระดับ transaction → ทำความสะอาด → รวมเป็นตาราง `date × article × qty`
  - แปลงราคา `"0,90 €"` → `0.90` (`parse_price`)
  - ตัดแถวที่ date/qty อ่านไม่ได้, article ว่างหรือเป็น `"."`, และ `qty <= 0` (การคืนของ/ยกเลิกบิล)
  - เลือกสินค้าขายดี top-N (`data.top_n_items = 15`) แล้วสร้างตารางครบทุกวัน × ทุกสินค้า เติม 0 ในวันที่ไม่มีขาย
  - cap ยอดที่เกิน Q99.9 ของสินค้านั้น (`data.outlier_quantile`)
  - บันทึก `data/processed/daily_sales.parquet` + `data/processed/meta.json` (data version = SHA256 ของไฟล์ดิบ, รายชื่อสินค้า, สถิติ mean/std/max ของช่วง train)
- `src/split.py` — `split_from_config()` แบ่ง train/val/test **ตามเวลา** ด้วยวันที่ใน config และ error ถ้ามีชุดไหนว่าง
- `src/validate.py` — Pandera schema ตรวจ 6 ข้อ: ชนิดข้อมูล/ค่าว่าง, `qty >= 0`, `article ∈ known_items`, `(date, article)` ไม่ซ้ำ, ไม่มีวันหาย, สถิติอยู่ในช่วง training
  - ไม่ผ่าน → log ERROR + เขียนต่อท้าย `logs/validation_alerts.log` + พิมพ์ตารางจุดผิด + **exit code 1**
- `data/samples/meta.json` — meta ของไฟล์ตัวอย่าง ให้ CI ตรวจ `data/samples/` ได้โดยไม่ต้องมีข้อมูลจริง
- `tests/test_data.py` — 10 tests (แปลงราคา, ตัดคืนของ, เติมวันหาย, top-N, cap, ไฟล์ดี/เสีย, ซ้ำ/วันหาย, สถิติผิดปกติ, exit code, split ว่าง)

### การตัดสินใจและเหตุผล
- **ตัด `qty <= 0` ทิ้ง แทนการ clip เป็น 0** — แถวติดลบคือการคืนของ ไม่ใช่ความต้องการซื้อ ถ้าเอามารวมจะทำให้ยอดของวันนั้นต่ำกว่าความจริง
- **เติม 0 ในวันที่ไม่มีขาย (รวมวันที่ร้านปิด)** — ให้ lag/rolling ของ P3 นับวันได้ถูก (lag_7 = 7 วันจริง ไม่ใช่ 7 แถว)
- **cap ที่ Q99.9 แทนการลบแถว** — ยอดสูงมาก ๆ อาจเป็นออเดอร์จัดเลี้ยงจริง ลบทิ้งจะทำให้วันหาย แต่ถ้าปล่อยไว้ loss จะถูกดึงด้วยวันเดียว
- **คำนวณเพดาน cap และสถิติอ้างอิงจากช่วง train เท่านั้น** — กันข้อมูลของ val/test รั่วเข้ามา (leakage)
- **แบ่งตามเวลา ไม่สุ่ม** — งานนี้คือทำนายอนาคต ถ้าสุ่มโมเดลจะเห็นยอดของวันหลังวันที่ทำนาย ได้คะแนนดีเกินจริง
- **Pandera `lazy=True` + `coerce=True`** — แปลงชนิดก่อนตรวจ (`"abc"`, `"2022-13-45"` ถูกจับ) และรวบรวม error ทุกจุดในครั้งเดียว แทนที่จะหยุดที่จุดแรก
- **เกณฑ์สถิติ**: mean ของ batch ต้องอยู่ใน `mean_train ± 3·std_train` และ max ต้องไม่เกิน `3 × max_train` — จับค่าที่พิมพ์ผิด/ระบบส่งมาผิดหน่วยได้ โดยไม่ล้มกับวันขายดีปกติ

### ผลลัพธ์ / หลักฐาน
- `python -m src.validate data/samples/bad_sales.csv` → **exit 1** พบ 12 จุดผิด ครอบคลุม: `qty = -5`, วันที่ `2022-13-45`, `UNKNOWN ITEM`, `qty = abc`, `qty` ว่าง, `(date, article)` ซ้ำ, มีวันหาย
- `python -m src.validate data/samples/good_sales.csv` → **exit 0**
- `ruff check .` ผ่าน · `pytest -q` ผ่าน 16 tests
- ทดสอบ `ingest → validate → split` ครบวงจรกับไฟล์ดิบจำลองรูปแบบเดียวกับ Kaggle (20 สินค้า, 2021-01-02 ถึง 2022-09-30) → ได้ 15 สินค้า × 637 วัน, validate ผ่าน, split ไม่มีชุดว่าง
- **ผลกับข้อมูลจริง (Kaggle Bakery sales.csv):**
  - clean: ตัดแถวเสีย 5 แถว, ตัดแถวคืนของ (qty <= 0) 1,295 แถว → เหลือ 232,705 transactions
  - cap ที่ Q99.9 (เพดานจากช่วง train) 34 แถว
  - ได้ 9,555 แถว = 15 สินค้า × 637 วัน (2021-01-02 ถึง 2022-09-30)
  - data version (SHA256): `af5eede55b6eb2efb6bebb0e6dd1a51568c7eb73554d2f8ad2563081025681b2`
  - 15 สินค้า: BAGUETTE, BANETTE, BOULE 400G, CAMPAGNE, CEREAL BAGUETTE, COOKIE, COUPE, CROISSANT, ECLAIR, FORMULE SANDWICH, PAIN AU CHOCOLAT, SPECIAL BREAD, TARTELETTE, TRADITIONAL BAGUETTE, VIK BREAD
  - สถิติช่วง train (ใช้ตรวจ anomaly): mean 27.44, std 50.61, max 538 ชิ้น/วัน
  - `python -m src.validate` กับไฟล์ processed → PASSED
  - split: train 2021-01-02 → 2022-06-30 (8,175 แถว) · val 2022-07-01 → 2022-08-31 (930 แถว) · test 2022-09-01 → 2022-09-30 (450 แถว)
  - screenshot ไฟล์เสียถูกจับ: `docs/evidence/p2_bad_data_caught.png`

### ปัญหาที่เจอและวิธีแก้
- CI ไม่มีไฟล์ข้อมูลจริง (gitignored) จึงไม่มี `meta.json` → ให้ `validate` ใช้ `data/samples/meta.json` แทนอัตโนมัติเมื่อยังไม่เคยรัน ingest
- ไฟล์จริงมีสินค้าชื่อ `"."` → ตัดออกตอน clean

### การใช้ AI
- ใช้ Claude Code ช่วยเขียน `ingest.py`, `validate.py`, `split_from_config()`, `tests/test_data.py` และร่าง section นี้; ตรวจสอบโดยรัน `ruff` + `pytest` และลองรันกับไฟล์ดี/เสีย (M2 ต้องอ่านและอธิบายได้ทุกบรรทัดก่อน merge)

### วิธีรัน/ทดสอบส่วนนี้
```bash
# 1) วาง "Bakery sales.csv" จาก Kaggle ไว้ที่ data/raw/
python -m src.ingest                                   # → data/processed/daily_sales.parquet + meta.json
python -m src.validate                                 # ตรวจไฟล์ processed (ผ่าน = exit 0)
python -m src.split                                    # ดูช่วงวันที่/จำนวนแถวของ train/val/test
# 2) สาธิตข้อมูลเสีย
python -m src.validate data/samples/bad_sales.csv; echo $?   # → 1
pytest -q tests/test_data.py
```

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
