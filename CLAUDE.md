# CLAUDE.md — Bakery Daily Demand Prediction (CP413008 MLOps Project)

> ไฟล์นี้เป็น "คู่มือทำงาน" ของทีมและของ Claude/AI ที่ช่วยเขียนโค้ดใน repo นี้
> ทุกคน (และ AI) ต้องอ่านไฟล์นี้ก่อนเริ่มงานทุกครั้ง

---

## 0. ข้อมูลโปรเจค

| หัวข้อ | รายละเอียด |
|---|---|
| รายวิชา | CP413008 Machine Learning Engineering for Production (ภาคเรียนที่ 1/2569) |
| โจทย์ | พยากรณ์ยอดขายรายสินค้าของ "วันพรุ่งนี้" และแนะนำจำนวนที่ควรเตรียม สำหรับร้านเบเกอรี่ |
| Pain point | เจ้าของร้านไม่รู้ว่าพรุ่งนี้สินค้าแต่ละชนิดจะขายได้กี่ชิ้น → เตรียมขาด (เสียยอดขาย) หรือเตรียมเกิน (ของเหลือทิ้ง) |
| Output ของระบบ | (1) ยอดขายคาดการณ์ p50 และ p_q  (2) จำนวนที่ควรเตรียม/สั่ง |
| Dataset | Kaggle: **French Bakery Daily Sales** (transaction-level, 2021–2022) → aggregate เป็น `date × article` |
| **กำหนดส่ง** | **5 ต.ค. 2569 เวลา 23:59 น.** |
| นำเสนอ | 12 ต.ค. 2569 08:30 น. — 12 นาที + ถามตอบ 3 นาที + Test case จากอาจารย์ (ปกติ/ผิดปกติ) |

### สมาชิก (แก้ placeholder ให้เป็นชื่อจริง)

| รหัส | ชื่อ | GitHub | บทบาทหลัก |
|---|---|---|---|
| M1 | `<ชื่อ>` | `@<user>` | Project Lead / Problem Framing / Report & Architecture |
| M2 | `<ชื่อ>` | `@<user>` | Data Engineer — Ingest, Split, Validation, Pipeline DAG |
| M3 | `<ชื่อ>` | `@<user>` | ML Engineer — Features, Training, Experiment Tracking |
| M4 | `<ชื่อ>` | `@<user>` | Serving Engineer — Registry Gate, API, Docker, Load Test |
| M5 | `<ชื่อ>` | `@<user>` | Ops Engineer — Monitoring, Drift, Retrain, CI/CD |

> ⚠️ อาจารย์ให้คะแนนรายบุคคลจาก **ประวัติ commit** + peer review + การตอบคำถาม
> → **ทุกคนต้อง commit และ push ด้วย account ของตัวเอง** และเปิด PR ของตัวเองอย่างน้อย 2 ครั้ง

---

## 1. กฎเหล็กของทีม (ทุกคน + AI ต้องทำตาม)

1. **ห้าม push ตรงเข้า `main` หรือ `dev`** — ทำงานบน `feature/*` เท่านั้น แล้วเปิด PR
2. **ทุก PR ต้องมี reviewer อย่างน้อย 1 คน** (ตามคู่ review ในหัวข้อ 4) และ CI ต้องผ่านก่อน merge
3. **ทำงานเสร็จแต่ละขั้นตอน → ต้องเขียนรายงานลง `report.md` ใน section ของขั้นนั้น ภายใน PR เดียวกัน**
   - PR ที่ไม่มีการอัปเดต `report.md` = ยังไม่เสร็จ (ห้าม merge)
   - แก้ **เฉพาะ section ของขั้นตัวเอง** เท่านั้น เพื่อลด merge conflict
4. **ห้าม commit ข้อมูลใหญ่/ความลับ** — `data/raw/*.csv`, `mlruns/`, `.env` อยู่ใน `.gitignore`
5. **ทุกอย่างต้องรันซ้ำได้ผลเดิม** — fix seed = `42`, pin version ใน `requirements.txt` (`==`)
6. **ใช้ AI ช่วยเขียนโค้ดได้ แต่ต้องบันทึกใน `report.md` (หัวข้อ "การใช้ AI") ว่าใช้ช่วยส่วนไหน** และเจ้าของงานต้องอธิบายได้ทุกบรรทัด
7. ก่อนเริ่มงานทุกครั้ง: `git checkout dev && git pull` แล้วค่อยแตก branch ใหม่

### กฎสำหรับ Claude / AI ที่ทำงานใน repo นี้
- ทำงานทีละขั้นตาม Phase ในหัวข้อ 5 และตรวจ "Definition of Done" ให้ครบก่อนบอกว่าเสร็จ
- เมื่อทำขั้นใดเสร็จ **ต้องอัปเดต section ของขั้นนั้นใน `report.md` เสมอ** ตามเทมเพลต (หัวข้อ 7)
- ห้ามแก้ section ของขั้นอื่นใน `report.md` และห้ามเขียนไฟล์นอกขอบเขตของขั้นที่ได้รับมอบหมาย
- ฟังก์ชันแปลงข้อมูลต้องอยู่ที่ `src/features.py` ที่เดียว และ API ต้อง import จากที่นั่น (กัน Training–Serving Skew)
- โค้ดต้องผ่าน `ruff check .` และ `pytest` ก่อนเสนอให้ commit
- อธิบายโค้ดเป็นภาษาไทยแบบสั้น ๆ ใน docstring/คอมเมนต์จุดสำคัญ เพื่อให้สมาชิกอธิบายตอนนำเสนอได้

---

## 2. Tech Stack (เหตุผลต้องเขียนใน report.md §2)

| หน้าที่ (ตามโจทย์) | เครื่องมือ | เหตุผลสั้น ๆ |
|---|---|---|
| Version Control | Git + GitHub | ใช้ร่วมกับ GitHub Actions ได้ทันที |
| Containerization | Docker + docker compose | รันทุก service ด้วยคำสั่งเดียวจากเครื่องเปล่า |
| Data Validation | Pandera | schema เป็นโค้ด Python, raise error ทันทีเมื่อเจอข้อมูลเสีย |
| Experiment Tracking | MLflow Tracking | log params/metrics/artifacts/tags ได้ครบ 6 อย่าง |
| Model Registry | MLflow Model Registry (alias `champion` / `challenger`) | promote / rollback ด้วยการย้าย alias |
| Pipeline Orchestration | Prefect 2 | Python ล้วน, เป็น DAG, รันบน Windows ได้ (Airflow ไม่รองรับ Windows native) |
| Model Serving | FastAPI + Uvicorn | Pydantic validate input → ตอบ 422 กับข้อมูลผิดปกติ |
| Monitoring | Evidently (drift) + Prometheus + Grafana (system) | แยก data drift / concept drift / system health |
| CI/CD | GitHub Actions | ตรวจ code quality, data validation, model gate |
| Model | LightGBM (quantile regression) | ทำนาย p50 และ p_q ได้ตรง ๆ, เร็ว, โมเดลเล็ก |
| Load test | Locust | วัด p50 / p95 latency และ throughput |

---

## 3. โครงสร้าง Repository

```
bakery-demand-mlops/
├─ CLAUDE.md                 # ไฟล์นี้
├─ README.md                 # วิธีรันจากเครื่องเปล่า (ต้องทดสอบจริง)
├─ report.md                 # รายงานรวม — แต่ละขั้นเขียน section ของตัวเอง
├─ requirements.txt          # pin version ทั้งหมด (==)
├─ ruff.toml                 # กฎ lint ของทีม
├─ docker-compose.yml        # mlflow, api, prometheus, grafana
├─ Dockerfile                # สำหรับ api / pipeline
├─ Makefile                  # make pipeline / make serve / make test / make loadtest
├─ configs/
│  └─ config.yaml            # path, split dates, quantile, thresholds, SLO
├─ data/
│  ├─ raw/                   # (gitignored) Bakery sales.csv จาก Kaggle
│  ├─ processed/             # (gitignored) daily_sales.parquet
│  └─ samples/               # (commit ได้) ไฟล์ตัวอย่างเล็ก + ไฟล์ข้อมูลเสียสำหรับสาธิต
├─ src/
│  ├─ ingest.py              # อ่าน csv → ทำความสะอาด → aggregate รายวัน×รายสินค้า
│  ├─ validate.py            # Pandera schema + ตรวจ anomaly → raise + alert
│  ├─ split.py               # time-based split (ไม่สุ่ม)
│  ├─ features.py            # build_features() ใช้ร่วม train/serve
│  ├─ train.py               # train + log MLflow ครบ 6 อย่าง
│  ├─ evaluate_gate.py       # เทียบกับ baseline/champion → promote หรือ reject
│  ├─ registry.py            # promote / rollback alias
│  ├─ recommend.py           # newsvendor → จำนวนที่ควรเตรียม
│  ├─ monitor.py             # Evidently data drift + concept drift (rolling WAPE)
│  ├─ simulate_drift.py      # สร้างข้อมูล drift สำหรับสาธิต
│  └─ flow.py                # Prefect DAG: ingest→validate→split→train→gate→register→batch predict
├─ api/
│  ├─ main.py                # /predict /recommend /health /metrics
│  └─ schemas.py             # Pydantic request/response
├─ monitoring/
│  ├─ prometheus.yml
│  └─ grafana/               # dashboard json
├─ loadtest/locustfile.py
├─ tests/                    # pytest: unit + data + api
├─ docs/
│  ├─ ai_project_canvas.md
│  ├─ architecture.png       # แผนภาพสถาปัตยกรรม
│  └─ evidence/              # screenshot: CI pass/fail, MLflow, Grafana, rollback
└─ .github/
   ├─ workflows/ci.yml
   └─ pull_request_template.md
```

---

## 4. Git Workflow: `main` + `dev` + `feature/*`

```
main  ──●──────────────────────────●───────── (release: v0.1, v1.0)
         \                        /
dev       ●──●──●──●──●──●──●──●─●──────────── (integration)
              \   /  \   /  \  /
feature/*      ●─●    ●─●    ●●
```

### Branch naming
`feature/<phase>-<สั้นๆ>` เช่น `feature/p2-data-validation`, `feature/p5-fastapi`
แก้บั๊ก: `fix/<สั้นๆ>` · เอกสาร: `docs/<สั้นๆ>`

### Commit message (Conventional Commits)
```
feat(data): add pandera schema for daily sales
fix(api): return 422 when quantity is negative
docs(report): write section 3 data validation
test(features): ensure same output for train and serve
ci: add model quality gate job
```

### ขั้นตอนทำงานมาตรฐาน (ทุกคน)
```bash
git checkout dev
git pull origin dev
git checkout -b feature/p2-data-validation
# ... เขียนโค้ด + อัปเดต report.md section ตัวเอง ...
ruff check . && pytest -q
git add .
git commit -m "feat(data): add pandera schema and bad-data demo"
git push -u origin feature/p2-data-validation
# เปิด PR: base = dev, ใส่ reviewer ตามคู่ด้านล่าง
```

### คู่ Review (ทุกคนได้ review งานคนอื่นด้วย)
M1 → review M2 · M2 → review M3 · M3 → review M4 · M4 → review M5 · M5 → review M1

### Branch protection (M1 ตั้งค่าใน GitHub → Settings → Branches)
- `main`, `dev`: Require pull request, Require 1 approval, Require status checks (CI) to pass

### Release
- จบ Day 2 → PR `dev → main` แท็ก `v0.1`
- ก่อนส่ง 5 ต.ค. → PR `dev → main` แท็ก `v1.0` (เวอร์ชันที่ส่งอาจารย์)

---

## 5. แผนงานและขั้นตอน (Phase)

### Timeline

| วัน | Phase | ผู้รับผิดชอบ |
|---|---|---|
| **Day 1 — เสาร์ 3 ต.ค.** | P0 Setup, P1 Framing, P2 Data, P3 Features+Baseline (เริ่ม) | ทุกคน |
| **Day 2 — อาทิตย์ 4 ต.ค.** | P3 Experiments, P4 Registry, P5 Serving, P6 Monitoring, P7 DAG | M3, M4, M5, M2 |
| **Day 3 — จันทร์ 5 ต.ค.** | P8 CI/CD, P9 Integration + Report + README (ทดสอบเครื่องเปล่า) → **ส่ง 23:59** | ทุกคน |
| 6–11 ต.ค. | P10 สไลด์ + ซ้อม + เตรียม test case | ทุกคน |
| 12 ต.ค. | นำเสนอ | ทุกคน |

---

### P0 — Setup Repository  `[M1 นำ, ทุกคนทำ]`
- [ ] M1 สร้าง repo, branch `dev`, ตั้ง branch protection, เพิ่ม collaborators 4 คน
- [ ] M1 push โครงโฟลเดอร์, `.gitignore`, `requirements.txt`, `CLAUDE.md`, `report.md`, PR template
- [ ] **ทุกคน**: clone → สร้าง `feature/p0-<ชื่อ>` → เพิ่มชื่อตัวเองในตารางสมาชิกของ `report.md` → PR (ทดสอบว่าทุกคน push ได้)
- [ ] ทุกคนสร้าง env: `conda create -n bakery python=3.11 -y && conda activate bakery && pip install -r requirements.txt`
- **DoD:** ทุกคนมี ≥1 commit ใน `dev`, report.md §0 ครบ

### P1 — Problem Framing  `[M1]`
- [ ] AI Project Canvas ครบทุกช่อง → `docs/ai_project_canvas.md`
- [ ] ตอบ 5 คำถามตรวจสอบหัวข้อ (ใครเดือดร้อน / business metric / drift / latency / rollback)
- [ ] เหตุผลที่ ML ดีกว่า rule (rule = seasonal-naive "เท่าวันเดียวกันสัปดาห์ก่อน" → ต้องชนะให้ได้)
- [ ] กำหนด metrics และ SLO ใส่ `configs/config.yaml`:
  - Optimizing: **WAPE** (ต่ำสุด) + Pinball loss @ q
  - Gating: WAPE ดีกว่า seasonal-naive ≥ 10% · p95 latency < 200 ms · model < 50 MB · ผ่าน schema
  - Business: stockout rate, waste rate, lost profit/วัน (simulate บน test set)
  - SLO: availability ≥ 99%, p95 < 200 ms, error rate < 1%, batch เสร็จก่อน 06:00
- **DoD:** canvas + config + report.md §1

### P2 — Data Ingestion, Split & Validation  `[M2]`
- [ ] `ingest.py`: แปลง `unit_price` ("0,90 €" → 0.90), รวม `Quantity` เป็น `date × article`, เติมวันที่ไม่มีขาย = 0, เลือก top-N สินค้า (เช่น 15)
- [ ] จัดการ missing / outlier: Quantity ติดลบ (คืนของ) → ตัดหรือ clip, ยอดผิดปกติ > Q99.9 → cap พร้อมเหตุผล
- [ ] `split.py` **แบ่งตามเวลา** (ห้ามสุ่ม) — วันที่แบ่งอยู่ใน config
- [ ] `validate.py` Pandera schema: ชนิดข้อมูล, `qty >= 0`, `article ∈ known_items`, วันที่ไม่ซ้ำ, ไม่มีวันหาย, สถิติ (mean/std) อยู่ในช่วงจาก training
- [ ] **สาธิตข้อมูลเสีย**: `data/samples/bad_sales.csv` → pipeline หยุด + log/alert (exit code ≠ 0)
- [ ] บันทึก data version = SHA256 ของไฟล์ raw
- **DoD:** `python -m src.validate data/samples/bad_sales.csv` ล้มพร้อมข้อความชัดเจน, tests ผ่าน, report.md §2

### P3 — Features, Training & Experiment Tracking  `[M3]`
- [ ] `features.py` → `build_features(history_df, target_date)`: lag_1, lag_7, lag_14, rolling_mean_7/28, rolling_std_7, day_of_week, month, is_weekend, is_holiday (France), item encoding
- [ ] test: feature จาก train path == serve path (กัน skew)
- [ ] `train.py` log MLflow ครบ 6 อย่าง:
  1. code version (`git rev-parse HEAD` → tag)
  2. data version (SHA256 → tag)
  3. hyperparameters
  4. metrics (WAPE, MAE, pinball, stockout/waste)
  5. artifacts (model, feature list, plots, SHAP)
  6. environment (`requirements.txt`, python version)
- [ ] ทดลอง **≥ 4 รอบ**: (1) Seasonal-naive (2) Linear Regression (3) LightGBM default (4) LightGBM tuned + holiday
- [ ] ตารางเปรียบเทียบ + เหตุผลเลือกโมเดลสุดท้าย + SHAP feature importance
- **DoD:** MLflow UI เห็นทุก run ครบ 6 อย่าง, report.md §3–§4

### P4 — Model Registry, Gate & Rollback  `[M4]`
- [ ] `evaluate_gate.py`: ผ่าน gating metric ทุกข้อ → register เป็น `challenger`; ชนะ `champion` → promote
- [ ] สถานะ: `challenger` / `champion` / `archived`
- [ ] `registry.py rollback` → ย้าย alias `champion` กลับเวอร์ชันก่อน, API reload ได้
- [ ] สาธิต: v1 champion → v2 (แย่กว่า) ถูก reject / หรือ promote แล้ว rollback กลับ v1
- **DoD:** screenshot registry + คำสั่ง rollback ใช้ได้จริง, report.md §5

### P5 — Serving, Docker & Load Test  `[M4]`
- [ ] FastAPI:
  - `POST /predict` `{article, date}` → `{p50, p_q, model_version}`
  - `POST /recommend` `{article, date, on_hand, unit_price, unit_cost}` → `{forecast, recommended_qty, q}`
  - `GET /health` (สถานะ + model version) · `GET /metrics` (Prometheus)
- [ ] Pydantic validation → **422** กับ: qty/price ติดลบ, article ไม่รู้จัก, date ผิดรูปแบบ/ไกลเกิน, field หาย, ชนิดผิด
- [ ] Logging ทุก request (JSON log: request_id, latency, version, input, output)
- [ ] `recommend.py` newsvendor: `q = (price - cost)/price`, `qty = max(0, ceil(F_q) - on_hand)`
- [ ] `Dockerfile` + `docker-compose.yml` (mlflow, api, prometheus, grafana)
- [ ] Serving pattern: **Batch** (Prefect รันทุกคืนพยากรณ์ทุกสินค้า) + **Real-time API** (ถามรายสินค้า) → อธิบายเหตุผล
- [ ] Locust: วัด p50/p95 latency + throughput (RPS) → เทียบ SLO
- **DoD:** `docker compose up` แล้ว `curl` จากเครื่องอื่นได้, ตาราง latency vs SLO, report.md §6

### P6 — Monitoring, Drift & Retraining  `[M5]`
- [ ] System: Prometheus + Grafana — request count, error rate, p95 latency, uptime
- [ ] Prediction quality: rolling 7-day WAPE (เมื่อได้ยอดขายจริงย้อนหลัง)
- [ ] `simulate_drift.py`:
  - **Data Drift** (P(X) เปลี่ยน): เลื่อน distribution ของ feature/สัดส่วนสินค้า → Evidently PSI/KS
  - **Concept Drift** (P(y|X) เปลี่ยน): feature เหมือนเดิม แต่ยอดจริง × 0.6 (คู่แข่งเปิด) → WAPE พุ่ง
- [ ] เกณฑ์แจ้งเตือน: PSI > 0.2 (data drift) · WAPE_7d > 1.2 × WAPE ตอน deploy (concept drift) · p95 > 200 ms · error > 1%
- [ ] นโยบาย retrain: ทุกสัปดาห์ (schedule) **หรือ** เมื่อเกิด alert ข้างบน → สาธิตวงจร ตรวจพบ → trigger flow → โมเดลใหม่ → gate → registry
- **DoD:** Evidently report html + Grafana screenshot + demo retrain, report.md §7

### P7 — Pipeline DAG  `[M2]`
- [ ] `flow.py` (Prefect): `ingest → validate → split → train → evaluate_gate → register → batch_predict`
- [ ] รันด้วยคำสั่งเดียว: `make pipeline` (หรือ `python -m src.flow`)
- [ ] validate fail → flow หยุด ไม่ train ต่อ
- **DoD:** screenshot DAG ใน Prefect UI, report.md §8

### P8 — CI/CD (GitHub Actions)  `[M5]`
- [ ] Job 1 **Code quality**: `ruff check .` + `pytest`
- [ ] Job 2 **Data validation**: รัน schema กับ `data/samples/` (ไฟล์ดีต้องผ่าน, ไฟล์เสียต้องถูกจับ)
- [ ] Job 3 **Model quality gate**: เทรนบน sample → ต้องผ่าน gating metric
- [ ] Job 4 (CD): build Docker image (push GHCR ถ้าทัน)
- [ ] **เก็บหลักฐานทั้งครั้ง PASS และครั้ง FAIL** (เปิด PR จงใจทำให้พัง เช่น ลด threshold / ใส่ข้อมูลเสีย) → `docs/evidence/`
- **DoD:** badge CI + screenshot pass/fail, report.md §9

### P9 — Integration, README, Architecture & Final Report  `[M1 นำ, ทุกคนตรวจ]`
- [ ] แผนภาพสถาปัตยกรรม `docs/architecture.png`
- [ ] README: ขั้นตอนรันจากเครื่องเปล่า → **ให้สมาชิก 1 คน clone ใหม่บนเครื่องที่ไม่เคยรันแล้วทดสอบจริง**
- [ ] รวม report.md ให้ครบทุก section + การใช้ AI + สรุป
- [ ] PR `dev → main` → tag `v1.0` → **ส่งก่อน 5 ต.ค. 23:59**

### P10 — นำเสนอ (6–11 ต.ค.)  `[ทุกคน]`
- [ ] สไลด์ 12 นาที — แต่ละคนพูดส่วนที่ตัวเองทำ (~2 นาที/คน)
- [ ] สคริปต์ demo: pipeline 1 คำสั่ง → ข้อมูลเสียถูกจับ → API predict/recommend → drift alert → retrain → rollback
- [ ] ซ้อม test case ผิดปกติ (input แปลก ๆ) และเตรียมคำตอบคำถามเทคนิค

---

## 6. คำสั่งที่ใช้บ่อย

```bash
make pipeline      # รันทั้ง DAG: raw → serving
make serve         # docker compose up -d
make test          # ruff + pytest
make loadtest      # locust headless → รายงาน p50/p95/RPS
make drift         # simulate drift + Evidently report
make rollback      # ย้าย champion กลับเวอร์ชันก่อน
```
URLs: API `http://localhost:8000/docs` · MLflow `:5000` · Prefect `:4200` · Prometheus `:9090` · Grafana `:3000`

> Windows: ใช้ Anaconda Prompt / PowerShell, ถ้าไม่มี `make` ให้รันคำสั่งใน Makefile ตรง ๆ หรือ `choco install make`

---

## 7. เทมเพลต section ใน report.md (ใช้ทุกขั้น)

```markdown
## §<เลข> <ชื่อขั้น>
**ผู้รับผิดชอบ:** M? (@github) · **Reviewer:** M? · **PR:** #<เลข> · **วันที่เสร็จ:** YYYY-MM-DD

### สิ่งที่ทำ
- ...

### การตัดสินใจและเหตุผล
- เลือก X เพราะ ... (เทียบกับทางเลือก Y)

### ผลลัพธ์ / หลักฐาน
- ตาราง/ตัวเลข/screenshot (`docs/evidence/...`)

### ปัญหาที่เจอและวิธีแก้
- ...

### การใช้ AI
- ใช้ <เครื่องมือ> ช่วย <ส่วนไหน>; ตรวจสอบโดย <วิธี>

### วิธีรัน/ทดสอบส่วนนี้
```bash
...
```
```

---

## 8. Definition of Done รวม (ตรวจก่อนส่ง 5 ต.ค.)

- [ ] ทุกคนมี commit + PR ของตัวเอง (ดู Insights → Contributors)
- [ ] `report.md` ครบ §0–§10 และมีหัวข้อการใช้ AI
- [ ] รันจากเครื่องเปล่าตาม README ได้
- [ ] สาธิต: ข้อมูลเสีย → หยุด+แจ้งเตือน
- [ ] train/serve ใช้ `build_features()` เดียวกัน
- [ ] MLflow ครบ 6 อย่าง, ≥ 3 การทดลอง, มีเหตุผลการเลือก
- [ ] Registry: gate + rollback ใช้ได้จริง
- [ ] API ใน container, /health, /metrics, logs, 422 กับ input ผิด
- [ ] p50/p95 + throughput เทียบ SLO
- [ ] แยก data drift / concept drift + เกณฑ์ alert + retrain demo
- [ ] CI 3 ด้าน + หลักฐาน pass และ fail
- [ ] DAG รันคำสั่งเดียว raw → serving
- [ ] แผนภาพสถาปัตยกรรม
