"""P6 (M5) — สร้างข้อมูลจำลอง Data Drift (P(X) เปลี่ยน) และ Concept Drift (P(y|X) เปลี่ยน)

ข้อมูลเข้า/ออกเป็นตารางรายวัน date × article × qty (รูปแบบเดียวกับ data/processed/daily_sales.parquet)
และเพิ่มคอลัมน์ `actual` = ยอดขายจริงที่ใช้วัด error ของโมเดล

    ┌──────────────┬──────────────────────────────┬──────────────────────────────┐
    │ scenario     │ qty (ใช้สร้าง feature = X)     │ actual (ยอดจริง = y)           │
    ├──────────────┼──────────────────────────────┼──────────────────────────────┤
    │ normal       │ เหมือนเดิม                     │ = qty                        │
    │ data_drift   │ ครึ่งหนึ่งของสินค้า × 1.5 (ช่วงท่องเที่ยว) │ = qty  (ความสัมพันธ์ X→y เดิม)   │
    │ concept_drift│ เหมือนเดิม                     │ = qty × 0.6 (คู่แข่งเปิดร้าน)      │
    └──────────────┴──────────────────────────────┴──────────────────────────────┘

    - Data drift: input เปลี่ยน → lag/rolling และสัดส่วนสินค้าเลื่อน → PSI สูง
    - Concept drift: input เหมือนเดิมทุกอย่าง แต่ลูกค้าซื้อน้อยลง → PSI ปกติ แต่ WAPE พุ่ง
      (ต้องดูจาก error เท่านั้น — เป็นเหตุผลที่ต้อง monitor ทั้ง 2 แบบแยกกัน)

รัน:  python -m src.simulate_drift            → data/processed/drift/<scenario>.parquet ทั้ง 3 แบบ
      python -m src.simulate_drift --scenario concept_drift --factor 0.5
"""

from __future__ import annotations

import argparse
import logging

import pandas as pd

from src.config import ROOT, load_config

log = logging.getLogger("simulate_drift")

SCENARIOS = ("normal", "data_drift", "concept_drift")
DRIFT_DIR = ROOT / "data" / "processed" / "drift"


def default_start(df: pd.DataFrame, cfg: dict) -> pd.Timestamp:
    """วันที่เริ่ม drift = 1 สัปดาห์หลังเริ่มช่วง test → สัปดาห์แรกปกติ ให้เห็นจุดที่ WAPE เริ่มพุ่งในกราฟ"""
    test_start = pd.Timestamp(cfg["split"]["val_end"]) + pd.Timedelta(days=1)
    start = test_start + pd.Timedelta(days=cfg["monitoring"].get("drift_start_offset_days", 7))
    return min(start, pd.to_datetime(df["date"]).max())


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["date", "article", "qty"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["qty"] = out["qty"].astype(float)
    return out


def drifted_articles(articles) -> list[str]:
    """เลือกครึ่งหนึ่งของสินค้า (ลำดับคู่ตามชื่อ) แบบ deterministic → รันซ้ำได้ผลเดิม"""
    return sorted(set(articles))[::2]


def make_data_drift(df: pd.DataFrame, factor: float = 1.5, start=None) -> pd.DataFrame:
    """Data drift: ตั้งแต่ `start` ยอดของครึ่งหนึ่งของสินค้า × factor (สัดส่วนสินค้าเปลี่ยน + ระดับยอดเปลี่ยน)

    qty ที่เปลี่ยนจะไหลเข้า lag/rolling feature ของวันถัดไป → P(X) เลื่อน, actual = qty (P(y|X) เดิม)
    """
    out = _prepare(df)
    start = pd.Timestamp(start) if start is not None else out["date"].min()
    mask = (out["date"] >= start) & out["article"].isin(drifted_articles(out["article"]))
    out.loc[mask, "qty"] = (out.loc[mask, "qty"] * factor).round()
    out["actual"] = out["qty"]
    return out


def make_concept_drift(df: pd.DataFrame, factor: float = 0.6, start=None) -> pd.DataFrame:
    """Concept drift: feature เหมือนเดิม (qty ไม่แตะ) แต่ยอดขายจริง × factor (เช่น คู่แข่งเปิดร้าน)"""
    out = _prepare(df)
    start = pd.Timestamp(start) if start is not None else out["date"].min()
    out["actual"] = out["qty"]
    mask = out["date"] >= start
    out.loc[mask, "actual"] = (out.loc[mask, "qty"] * factor).round()
    return out


def make_normal(df: pd.DataFrame) -> pd.DataFrame:
    out = _prepare(df)
    out["actual"] = out["qty"]
    return out


def simulate(df: pd.DataFrame, scenario: str, cfg: dict, factor: float | None = None,
             start=None) -> pd.DataFrame:
    """สร้างข้อมูลตาม scenario (factor/start ไม่ระบุ → ใช้ค่าใน config)"""
    mon = cfg["monitoring"]
    start = start if start is not None else default_start(df, cfg)
    if scenario == "normal":
        return make_normal(df)
    if scenario == "data_drift":
        return make_data_drift(df, factor or mon.get("data_drift_factor", 1.5), start)
    if scenario == "concept_drift":
        return make_concept_drift(df, factor or mon.get("concept_drift_factor", 0.6), start)
    raise ValueError(f"unknown scenario '{scenario}' (ใช้ได้: {', '.join(SCENARIOS)})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="สร้างข้อมูลจำลอง drift (P6)")
    parser.add_argument("--scenario", choices=[*SCENARIOS, "all"], default="all")
    parser.add_argument("--factor", type=float, default=None, help="ตัวคูณ (ไม่ระบุ = ค่าใน config)")
    parser.add_argument("--start", default=None, help="วันที่เริ่ม drift YYYY-MM-DD (ไม่ระบุ = test_start + 7 วัน)")
    args = parser.parse_args(argv)

    cfg = load_config()
    src_path = ROOT / cfg["paths"]["processed"]
    if not src_path.exists():
        raise SystemExit(f"ไม่พบ {src_path} — รัน python -m src.ingest ก่อน")
    df = pd.read_parquet(src_path)

    DRIFT_DIR.mkdir(parents=True, exist_ok=True)
    scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
    for sc in scenarios:
        out = simulate(df, sc, cfg, args.factor, args.start)
        path = DRIFT_DIR / f"{sc}.parquet"
        out.to_parquet(path, index=False)
        log.info("บันทึก %s (%d แถว, drift เริ่ม %s)", path.relative_to(ROOT), len(out),
                 default_start(df, cfg).date() if args.start is None else args.start)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
