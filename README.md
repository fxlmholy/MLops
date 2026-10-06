# 🥖 Bakery Daily Demand Prediction — CP413008 MLOps Project

[![CI](https://github.com/fxlmholy/MLops/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/fxlmholy/MLops/actions/workflows/ci.yml)

พยากรณ์ยอดขายรายสินค้าของวันพรุ่งนี้ และแนะนำจำนวนที่ควรเตรียม (Newsvendor) สำหรับร้านเบเกอรี่

> คู่มือทีม: [`CLAUDE.md`](CLAUDE.md) · รายงาน: [`report.md`](report.md)

## รันจากเครื่องเปล่า
```bash
git clone <repo-url> && cd bakery-demand-mlops
conda create -n bakery python=3.11 -y && conda activate bakery
pip install -r requirements.txt

# 1) ดาวน์โหลด Kaggle "French Bakery Daily Sales" → วางไฟล์ที่ data/raw/Bakery sales.csv
# 2) เปิด service
docker compose up -d --build
# 3) รัน pipeline ทั้งหมด (raw → validate → train → gate → register → serve)
make pipeline
# 4) ทดสอบ API
curl -X POST http://localhost:8000/recommend -H "Content-Type: application/json" \
  -d '{"article":"TRADITIONAL BAGUETTE","date":"2022-09-15","on_hand":10,"unit_price":1.2,"unit_cost":0.4}'
```

| Service | URL |
|---|---|
| API docs | http://localhost:8000/docs |
| MLflow | http://localhost:5000 |
| Prefect | http://localhost:4200 |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

> TODO(P9/M1): ทดสอบขั้นตอนนี้บนเครื่องที่ไม่เคยรันจริง แล้วแก้ README ให้ตรง
