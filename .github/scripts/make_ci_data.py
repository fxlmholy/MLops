"""P8 (M5) — สร้างข้อมูลยอดขายรายวัน "สังเคราะห์" สำหรับ CI job model-gate

ทำไมต้องสังเคราะห์: ข้อมูลจริงจาก Kaggle ไม่ได้ commit ลง repo (ขนาดใหญ่ + license) และ GitHub Actions
ดาวน์โหลด Kaggle ไม่ได้ถ้าไม่มี API key → สร้างข้อมูลรูปแบบเดียวกับผลของ src.ingest
(date × article × qty, ช่วงวันที่ตรงกับ split ใน config) ให้ train → gate รันได้ครบในทุก PR

รูปแบบข้อมูล: Poisson(ฐานรายสินค้า × วันในสัปดาห์ × ฤดูร้อน) — มี pattern ที่โมเดลควรเรียนรู้ได้ดีกว่า
seasonal-naive ถ้าโค้ด train/feature พัง (เช่น lag รั่ว, feature หาย) WAPE จะไม่ผ่าน gate → CI แดง

รัน: python .github/scripts/make_ci_data.py   → data/processed/daily_sales.parquet (seed 42 → ได้ไฟล์เดิมทุกครั้ง)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.config import load_config  # noqa: E402

ARTICLES = [
    "TRADITIONAL BAGUETTE", "CROISSANT", "PAIN AU CHOCOLAT", "COUPE", "BANETTE",
    "BAGUETTE", "CEREAL BAGUETTE", "SPECIAL BREAD", "CAMPAGNE", "FICELLE",
    "BOULE 400G", "TARTELETTE", "BOULE 200G", "PAIN", "BANETTINE",
]
WEEKDAY = np.array([0.9, 0.85, 0.9, 0.95, 1.0, 1.35, 1.5])  # จ.–อา.


def make(cfg: dict) -> pd.DataFrame:
    rng = np.random.default_rng(cfg.get("seed", 42))
    dates = pd.date_range("2021-01-02", "2022-09-30", freq="D")
    articles = ARTICLES[: cfg["data"]["top_n_items"]]
    base = np.geomspace(150, 8, len(articles))
    season = np.where(dates.month.isin([7, 8]), 1.4, 1.0) * WEEKDAY[dates.dayofweek]
    lam = np.outer(season, base)                                  # วัน × สินค้า
    # DEMO FAIL: ยอดวันนี้ = ยอดวันเดียวกันสัปดาห์ก่อน + noise (random walk รายสัปดาห์)
    # → seasonal-naive คือคำตอบที่ดีที่สุดอยู่แล้ว โมเดลชนะ rule ไม่ถึง 10% → gate ต้อง REJECT
    qty = np.round(lam).astype(float)
    for t in range(7, len(dates)):
        qty[t] = np.maximum(0, qty[t - 7] + rng.normal(0, 0.15 * base))
    qty = np.round(qty)
    return pd.DataFrame({
        "date": np.repeat(dates.strftime("%Y-%m-%d"), len(articles)),
        "article": np.tile(articles, len(dates)),
        "qty": qty.ravel().astype(int),
    })


def main() -> None:
    cfg = load_config()
    out = ROOT / cfg["paths"]["processed"]
    out.parent.mkdir(parents=True, exist_ok=True)
    df = make(cfg)
    df.to_parquet(out, index=False)
    print(f"CI sample: {out.relative_to(ROOT)}  {len(df)} แถว, {df['article'].nunique()} สินค้า, "
          f"{df['date'].min()} → {df['date'].max()}")


if __name__ == "__main__":
    main()
