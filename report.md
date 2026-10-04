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
| 10 | Architecture, Reproducibility & สรุป | M1 | 🟨 |
| 11 | สรุปการใช้ AI (รวมจากทุก section) | M1 | 🟨 |

---

## §0 สมาชิกและการแบ่งงาน
<!-- P0: ทุกคนเพิ่มแถวของตัวเองผ่าน PR ของตัวเอง -->

| รหัส | ชื่อ-สกุล | รหัสนักศึกษา | GitHub | บทบาท |
|---|---|---|---|---|
| M1 | | 67xxxxxxxx | @nattapongsric-collab | Project Lead / Framing / Report |
| M2 | | 67xxxxxxxx | NongPP235 | Data Engineer |
| M3 | | | | ML Engineer |
| M4 | | | | Serving Engineer |
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
**ผู้รับผิดชอบ:** M1 (@nattapongsric-collab) · **Reviewer:** M5 (@thanachotkam-hue) · **PR:** # · **วันที่เสร็จ:** (รอทดสอบเครื่องเปล่า)

### แผนภาพสถาปัตยกรรม
![Architecture](docs/architecture.png)

ระบบแบ่งเป็น 5 ส่วน:

| ส่วน | หน้าที่ | เครื่องมือ | ผู้รับผิดชอบ |
|---|---|---|---|
| Training pipeline | ingest → validate → split → features → train → gate → register รันด้วยคำสั่งเดียว | Prefect 2, Pandera, LightGBM | M2, M3, M4 |
| Experiment tracking & Registry | log ครบ 6 อย่าง (code, data, params, metrics, artifacts, env) และจัดการ alias `champion`/`challenger` | MLflow | M3, M4 |
| Serving | Batch ทุกคืนก่อน 06:00 + Real-time API, คำนวณจำนวนที่ควรเตรียมแบบ newsvendor | FastAPI, Docker compose | M4 |
| Monitoring & Retraining | system health, data drift (PSI), concept drift (rolling WAPE) → alert → retrain | Prometheus, Grafana, Evidently | M5 |
| CI/CD | code quality, data validation, model gate, build image ทุก PR | GitHub Actions | M5 |

**จุดออกแบบสำคัญ**
- **กัน Training–Serving skew:** ทั้ง training และ API เรียก `build_features()` จาก `src/features.py` ที่เดียว
- **ข้อมูลเสียไม่หลุดเข้าโมเดล:** validate ไม่ผ่าน → flow หยุดก่อน train
- **โมเดลแย่ไม่ถูก deploy:** ต้องผ่าน gate ทุกข้อใน `configs/config.yaml` → `gate`
- **ย้อนกลับได้ทันที:** rollback = ย้าย alias `champion` ใน MLflow Registry ไม่ต้อง build ใหม่
- **ปิดวงจร:** monitoring ตรวจพบ drift → trigger training flow → gate → registry → API โหลด champion ใหม่

### Reproducibility
| สิ่งที่ล็อกไว้ | วิธี |
|---|---|
| Random seed | `seed: 42` ใน `configs/config.yaml` |
| Library | pin ทุกตัวด้วย `==` ใน `requirements.txt` |
| Code version | `git rev-parse HEAD` → MLflow tag |
| Data version | SHA256 ของไฟล์ raw → MLflow tag |
| Environment | Python 3.11 (conda) + Docker image `python:3.11-slim` |
| การแบ่งข้อมูล | แบ่งตามวันที่ใน config (ไม่สุ่ม) |
| ค่าตั้งทั้งหมด | `configs/config.yaml` ไฟล์เดียว |

### ผลทดสอบรันจากเครื่องเปล่า
> ทำหลังทุก phase merge เข้า `dev` — สมาชิก 1 คน clone ใหม่บนเครื่องที่ไม่เคยรัน แล้วทำตาม README ทีละขั้น

| ขั้นตอนใน README | ผล | หมายเหตุ / สิ่งที่ต้องแก้ |
|---|---|---|
| clone + `pip install -r requirements.txt` | ⬜ | |
| วาง `data/raw/Bakery sales.csv` | ⬜ | |
| `docker compose up -d --build` | ⬜ | |
| `make pipeline` | ⬜ | |
| `curl /recommend` | ⬜ | |
| `python -m src.validate data/samples/bad_sales.csv` ล้ม | ⬜ | |

ผู้ทดสอบ: · เครื่อง/OS: · วันที่:

### สรุปผลเชิงธุรกิจ
> ตัวเลขดึงจาก §4 (M3) เมื่อการทดลองเสร็จ

| ตัวชี้วัด | Seasonal-naive (rule) | โมเดลที่เลือก | เปลี่ยนแปลง |
|---|---|---|---|
| WAPE | | | |
| Stockout rate | | | |
| Waste rate | | | |
| Lost profit / วัน | | | |

### ข้อจำกัดและงานในอนาคต
- **ข้อมูลจากร้านเดียว ช่วง 2021–2022** — โมเดลอาจใช้กับร้านอื่นหรือช่วงเวลาอื่นไม่ได้ทันที ต้องเทรนใหม่ด้วยข้อมูลของร้านนั้น
- **ไม่มีข้อมูลสต็อกจริง** — ยอดขายที่เห็นคือยอดที่ขายได้ ไม่ใช่ความต้องการจริง วันที่ของหมดเร็วจะทำให้ประเมินความต้องการต่ำไป (censored demand)
- **ไม่มี feature ภายนอก** เช่น สภาพอากาศ, โปรโมชัน, อีเวนต์ในพื้นที่ — อนาคตเพิ่มได้ผ่าน `build_features()`
- **ต้นทุนสินค้าเป็นค่าสมมุติ** — q ของ newsvendor ขึ้นกับราคา/ต้นทุน ถ้าใช้จริงต้องใช้ต้นทุนจริงของร้าน
- **รันบนเครื่องเดียว** — ถ้าขยายหลายสาขา ควรแยก MLflow/DB ไปที่ server กลางและใช้ Prefect work pool

---

## §11 สรุปการใช้ AI
> M1 รวบรวมจากหัวข้อ "การใช้ AI" ของทุก section — แต่ละคนกรอกแถวของตัวเองใน section ของตัวเองก่อน แล้ว M1 สรุปมาที่นี่

| ส่วนของงาน | เครื่องมือ AI | ใช้ช่วยทำอะไร | ผู้ตรวจสอบ/อธิบายได้ |
|---|---|---|---|
| P0 Setup | Claude Code | ตั้งค่า git (ชื่อ/อีเมล), แตก branch, ช่วยเปิด PR | M1 |
| §1 Problem Framing | Claude Code | ร่างคำตอบ 5 คำถาม, เหตุผลเลือก metric, จัดตาราง metric/gate/SLO | M1 |
| §10 Architecture & README | Claude Code | ร่างแผนภาพสถาปัตยกรรม (สคริปต์ matplotlib), ปรับ README, ร่าง §10 | M1 |
| §2 Data | (รอ M2) | | M2 |
| §3–§4 Features & Model | (รอ M3) | | M3 |
| §5–§6 Registry & Serving | (รอ M4) | | M4 |
| §7 Monitoring | (รอ M5) | | M5 |
| §8 Pipeline DAG | (รอ M2) | | M2 |
| §9 CI/CD | (รอ M5) | | M5 |

**หลักการที่ทีมใช้:** AI ช่วยร่างโค้ด/เอกสารได้ แต่เจ้าของงานต้องอ่านทุกบรรทัด รันทดสอบเอง และอธิบายได้ตอนนำเสนอ (CLAUDE.md §1 ข้อ 6)
