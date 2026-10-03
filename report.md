# รายงานโครงงาน CP413008 — Bakery Daily Demand Prediction

> **กฎ:** แต่ละขั้นเขียนเฉพาะ section ของตัวเอง ภายใน PR ของขั้นนั้น (ดู CLAUDE.md §1 และ §7)
> สถานะ: ⬜ ยังไม่เริ่ม · 🟨 กำลังทำ · ✅ เสร็จ

| § | ขั้น | ผู้รับผิดชอบ | สถานะ |
|---|---|---|---|
| 0 | สมาชิกและการแบ่งงาน | M1 + ทุกคน | ⬜ |
| 1 | Problem Framing & AI Project Canvas | M1 | ⬜ |
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
| M1 | | | | Project Lead / Framing / Report |
| M2 | | | | Data Engineer |
| M3 | | | | ML Engineer |
| M4 | | | | Serving Engineer |
| M5 | | | | Ops Engineer |

---

## §1 Problem Framing & AI Project Canvas
**ผู้รับผิดชอบ:** M1 · **Reviewer:** M5 · **PR:** # · **วันที่เสร็จ:**

### สิ่งที่ทำ
### การตัดสินใจและเหตุผล
### ผลลัพธ์ / หลักฐาน
### ปัญหาที่เจอและวิธีแก้
### การใช้ AI
### วิธีรัน/ทดสอบส่วนนี้

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
