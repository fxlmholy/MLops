"""P2 (M2) — อ่าน csv ดิบ → ทำความสะอาด → aggregate เป็นยอดขายรายวัน × รายสินค้า

ไฟล์ดิบ (Kaggle: French Bakery Daily Sales) เป็นระดับ transaction:
    ,date,time,ticket_number,article,Quantity,unit_price
    0,2021-01-02,08:38,150040.0,BAGUETTE,1.0,"0,90 €"

ผลลัพธ์: ตาราง date × article × qty (1 แถว = ยอดขาย 1 สินค้าใน 1 วัน)
    + ไฟล์ meta.json (data version, รายชื่อสินค้า, สถิติ training) ให้ validate.py ใช้

รัน:  python -m src.ingest
"""

import json
import logging

import pandas as pd

from src.config import ROOT, load_config
from src.train import file_sha256

log = logging.getLogger("ingest")


def parse_price(text) -> float:
    """แปลงราคาแบบฝรั่งเศส "0,90 €" -> 0.90 (ถ้าอ่านไม่ได้คืน NaN)"""
    if pd.isna(text):
        return float("nan")
    cleaned = str(text).replace("€", "").replace("\xa0", "").strip().replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return float("nan")


def load_raw(path: str) -> pd.DataFrame:
    """อ่าน csv ดิบ → คอลัมน์ date, article, qty, unit_price (ยังเป็นระดับ transaction)"""
    df = pd.read_csv(path)
    df = df.rename(columns={"Quantity": "qty"})
    df = df[["date", "article", "qty", "unit_price"]].copy()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["article"] = df["article"].astype(str).str.strip().str.upper()
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
    df["unit_price"] = df["unit_price"].map(parse_price)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """ตัดแถวที่ใช้ไม่ได้ออก และ log ว่าตัดไปกี่แถว

    - date/qty อ่านไม่ได้ (NaN) → ตัด
    - article ว่าง หรือเป็น "." (ในไฟล์จริงมีสินค้าชื่อ ".") → ตัด
    - qty <= 0 = การคืนของ/ยกเลิกบิล ไม่ใช่ความต้องการซื้อ → ตัด
    """
    n0 = len(df)
    df = df.dropna(subset=["date", "qty"])
    df = df[~df["article"].isin(["", ".", "NAN"])]
    n_bad = n0 - len(df)

    n_neg = int((df["qty"] <= 0).sum())
    df = df[df["qty"] > 0]

    log.info("clean: ตัดแถวเสีย %d แถว, ตัดแถวคืนของ (qty<=0) %d แถว, เหลือ %d แถว", n_bad, n_neg, len(df))
    return df


def to_daily(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """รวม qty เป็น date × article, เลือกสินค้าขายดี top-N, เติมวันที่ไม่มีขาย = 0"""
    top_items = df.groupby("article")["qty"].sum().nlargest(top_n).index
    df = df[df["article"].isin(top_items)]

    daily = df.groupby(["date", "article"], as_index=False)["qty"].sum()

    # สร้างตารางครบทุกวัน × ทุกสินค้า แล้วเติม 0 วันที่ไม่มีขาย (รวมวันที่ร้านปิด)
    all_days = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    grid = pd.MultiIndex.from_product([all_days, sorted(top_items)], names=["date", "article"])
    daily = daily.set_index(["date", "article"]).reindex(grid, fill_value=0).reset_index()
    return daily


def cap_outliers(daily: pd.DataFrame, quantile: float, fit_end: str) -> pd.DataFrame:
    """cap ยอดที่สูงผิดปกติ (> quantile ของสินค้านั้น) ไว้ที่ค่า quantile

    คำนวณเพดานจากช่วง train เท่านั้น (date <= fit_end) เพื่อไม่ให้ข้อมูลอนาคตรั่วเข้ามา
    """
    fit = daily[daily["date"] <= fit_end]
    caps = fit.groupby("article")["qty"].quantile(quantile)
    limit = daily["article"].map(caps)
    n_capped = int((daily["qty"] > limit).sum())
    daily = daily.assign(qty=daily["qty"].clip(upper=limit))
    log.info("cap_outliers: cap ที่ Q%.1f จำนวน %d แถว", quantile * 100, n_capped)
    return daily


def build_meta(daily: pd.DataFrame, raw_path: str, fit_end: str) -> dict:
    """ข้อมูลประกอบที่ validate.py ใช้: data version, รายชื่อสินค้า, สถิติของช่วง train"""
    train = daily[daily["date"] <= fit_end]["qty"]
    return {
        "data_version": file_sha256(raw_path),
        "known_items": sorted(daily["article"].unique().tolist()),
        "train_stats": {
            "mean": round(float(train.mean()), 4),
            "std": round(float(train.std()), 4),
            "max": float(train.max()),
        },
        "date_min": str(daily["date"].min().date()),
        "date_max": str(daily["date"].max().date()),
        "n_rows": int(len(daily)),
    }


def run(cfg: dict | None = None) -> pd.DataFrame:
    """ทั้งขั้นตอน: raw csv → daily parquet + meta.json (เรียกจาก flow.py ได้)"""
    cfg = cfg or load_config()
    raw_path = ROOT / cfg["paths"]["raw"]
    out_path = ROOT / cfg["paths"]["processed"]
    meta_path = ROOT / cfg["paths"]["meta"]
    fit_end = cfg["split"]["train_end"]

    if not raw_path.exists():
        raise FileNotFoundError(f"ไม่พบไฟล์ดิบ {raw_path} — ดาวน์โหลดจาก Kaggle มาวางก่อน (ดู README)")

    df = clean(load_raw(raw_path))
    daily = to_daily(df, cfg["data"]["top_n_items"])
    daily = cap_outliers(daily, cfg["data"]["outlier_quantile"], fit_end)
    daily["date"] = daily["date"].dt.date.astype(str)  # เก็บเป็น "YYYY-MM-DD" ให้รูปแบบเดียวกับ samples
    daily["qty"] = daily["qty"].round().astype(int)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(out_path, index=False)

    meta = build_meta(daily.assign(date=pd.to_datetime(daily["date"])), raw_path, fit_end)
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info("บันทึก %s (%d แถว, %d สินค้า), data_version=%s",
             out_path, len(daily), len(meta["known_items"]), meta["data_version"][:12])
    return daily


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run()
