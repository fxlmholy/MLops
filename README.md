# 🥖 Bakery Daily Demand Prediction — CP413008 MLOps Project

พยากรณ์ยอดขายรายสินค้าของวันพรุ่งนี้ และแนะนำจำนวนที่ควรเตรียม (Newsvendor) สำหรับร้านเบเกอรี่

> คู่มือทีม: [`CLAUDE.md`](CLAUDE.md) · รายงาน: [`report.md`](report.md)

![Architecture](docs/architecture.png)

## สิ่งที่ต้องมีในเครื่อง
| เครื่องมือ | เวอร์ชัน | ใช้ทำอะไร |
|---|---|---|
| Git | ล่าสุด | clone repo |
| Anaconda / Miniconda | ล่าสุด | สร้าง env Python 3.11 |
| Docker Desktop | ล่าสุด (เปิดไว้ก่อนรัน) | MLflow, API, Prometheus, Grafana |
| make (ไม่บังคับ) | — | Windows: `choco install make` หรือรันคำสั่งในตารางด้านล่างตรง ๆ |

## รันจากเครื่องเปล่า
```bash
# 0) clone + สร้าง environment
git clone https://github.com/fxlmholy/MLops.git && cd MLops
conda create -n bakery python=3.11 -y && conda activate bakery
pip install -r requirements.txt

# 1) ดาวน์โหลด Kaggle "French Bakery Daily Sales"
#    วางไฟล์ไว้ที่ data/raw/Bakery sales.csv (ชื่อไฟล์ต้องตรง — ดู configs/config.yaml → paths.raw)

# 2) เปิด service ทั้งหมด (MLflow :5000, API :8000, Prometheus :9090, Grafana :3000)
docker compose up -d --build

# 3) รัน pipeline ทั้งหมดด้วยคำสั่งเดียว: ingest → validate → split → train → gate → register → batch predict
make pipeline            # หรือ: python -m src.flow

# 4) ทดสอบ API
curl -X POST http://localhost:8000/recommend -H "Content-Type: application/json"   -d '{"article":"TRADITIONAL BAGUETTE","date":"2022-09-15","on_hand":10,"unit_price":1.2,"unit_cost":0.4}'
```

> **Windows PowerShell:** ใช้ `curl.exe` แทน `curl` หรือเปิด http://localhost:8000/docs แล้วกด "Try it out"

## คำสั่งที่ใช้บ่อย
| คำสั่ง | ถ้าไม่มี make ให้รัน | ทำอะไร |
|---|---|---|
| `make pipeline` | `python -m src.flow` | รันทั้ง DAG raw → serving |
| `make serve` | `docker compose up -d --build` | เปิดทุก service |
| `make test` | `ruff check . && pytest -q` | lint + test |
| `make loadtest` | ดู `Makefile` | วัด p50/p95 latency + RPS |
| `make drift` | `python -m src.simulate_drift && python -m src.monitor` | สาธิต data/concept drift |
| `make rollback` | `python -m src.registry rollback` | ย้าย `champion` กลับเวอร์ชันก่อน |
| `make down` | `docker compose down` | ปิดทุก service |

## สาธิตข้อมูลเสีย
```bash
python -m src.validate data/samples/bad_sales.csv   # ต้องล้ม (exit code ≠ 0) พร้อมข้อความบอกว่าผิดตรงไหน
```

| Service | URL |
|---|---|
| API docs | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Prefect UI | http://localhost:4200 (เปิดด้วย `prefect server start` ใน terminal แยก) |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 (user/pass เริ่มต้น `admin` / `admin`) |

## โครงสร้าง repo
| โฟลเดอร์ | เนื้อหา |
|---|---|
| `src/` | pipeline: ingest, validate, split, features, train, gate, registry, monitor, flow |
| `api/` | FastAPI `/predict` `/recommend` `/health` `/metrics` |
| `configs/config.yaml` | ค่าทั้งหมด: path, split, metrics, gate, SLO, monitoring |
| `monitoring/` | Prometheus + Grafana dashboard |
| `tests/` | pytest |
| `docs/` | AI Project Canvas, architecture, หลักฐาน (`evidence/`) |

> สถานะ README: ร่างจากโครงสร้างที่ออกแบบไว้ — **ยังต้องให้สมาชิก 1 คน clone ใหม่บนเครื่องที่ไม่เคยรันแล้วทดสอบจริง** หลังทุก phase merge เข้า `dev` (ผลบันทึกใน report.md §10)
