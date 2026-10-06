"""P7 (M2) — Prefect DAG: ingest → validate → split → train → evaluate_gate → register → batch_predict

รันทั้ง pipeline ด้วยคำสั่งเดียว (ต้องเปิด MLflow ก่อน: `docker compose up -d mlflow`):
    make pipeline                      # = python -m src.flow
    python -m src.flow --data data/samples/bad_sales.csv   # สาธิตข้อมูลเสีย → flow หยุดที่ validate
    python -m src.flow --serve         # ตั้งเวลารันทุกคืน 02:00 (batch ต้องเสร็จก่อน 06:00 ตาม SLO)

หลักการ:
    - แต่ละขั้นเป็น @task เรียกฟังก์ชันของเจ้าของขั้นนั้นตรง ๆ (ไม่เขียน logic ซ้ำ)
    - task ไหน raise → task ถัดไปไม่ถูกเรียก → flow จบด้วยสถานะ Failed และ exit code 1
      เช่น validate ไม่ผ่าน → ไม่ train / ไม่ register / ไม่ batch predict
"""

import argparse
import os
import sys
import urllib.request

import pandas as pd
import pandera as pa
from prefect import flow, get_run_logger, task

from src import evaluate_gate, ingest, registry, split, train, validate
from src.config import ROOT, load_config

NIGHTLY_CRON = "0 2 * * *"  # 02:00 ทุกคืน


@task(name="ingest")
def ingest_task(cfg: dict) -> pd.DataFrame:
    """raw csv (Kaggle) → daily parquet + meta.json (data version = SHA256 ของไฟล์ raw)"""
    daily = ingest.run(cfg)
    meta = validate.load_meta(ROOT / cfg["paths"]["meta"])
    get_run_logger().info("ingest: %d แถว, %d สินค้า, data_version=%s",
                          len(daily), len(meta["known_items"]), meta["data_version"][:12])
    return daily


@task(name="load_file")
def load_file_task(path: str) -> pd.DataFrame:
    """โหมด --data: อ่านไฟล์รายวันที่ระบุแทนการ ingest (ใช้สาธิตไฟล์เสีย)"""
    return validate.read_any(path)


@task(name="validate")
def validate_task(df: pd.DataFrame, meta_path: str) -> pd.DataFrame:
    """Pandera schema — ไม่ผ่าน: alert (log + logs/validation_alerts.log) แล้ว raise ให้ flow หยุด"""
    logger = get_run_logger()
    meta = validate.load_meta(meta_path)
    try:
        checked = validate.validate(df, meta)
    except pa.errors.SchemaErrors as err:
        validate.alert(f"VALIDATION FAILED ใน pipeline — พบ {len(err.failure_cases)} จุดผิด → หยุด flow")
        logger.error("รายละเอียด:\n%s", validate.summarize_errors(err))
        raise
    logger.info("validate: ผ่าน (%d แถว)", len(checked))
    return checked


@task(name="split")
def split_task(df: pd.DataFrame, cfg: dict) -> dict:
    """ตรวจว่าแบ่งตามเวลาได้ครบ 3 ชุด (train.py แบ่งด้วยวันที่ชุดเดียวกันจาก config)"""
    parts = split.split_from_config(df, cfg)
    sizes = {}
    for name, part in zip(["train", "val", "test"], parts, strict=True):
        sizes[name] = len(part)
        dates = pd.to_datetime(part["date"])
        get_run_logger().info("split %-5s: %s → %s (%d แถว)",
                              name, dates.min().date(), dates.max().date(), len(part))
    return sizes


@task(name="train")
def train_task() -> None:
    """เทรน 4 โมเดล + log MLflow ครบ 6 อย่าง (src.train ของ M3)"""
    train.main()


@task(name="evaluate_gate")
def gate_task(cfg: dict) -> dict:
    """เลือก candidate ที่ดีที่สุด → ตรวจ gating metric → ลงทะเบียน challenger / promote champion (M4)

    gate ไม่ผ่าน → raise ให้ flow หยุด (ไม่ batch predict ด้วยข้อมูลรอบนี้) เหมือน exit code 1 ของ
    `python -m src.evaluate_gate` — champion เดิมยังให้บริการต่อใน API
    """
    result = evaluate_gate.evaluate(cfg=cfg)
    if not result["passed_gate"]:
        raise RuntimeError("model gate REJECTED: " + "; ".join(result["reasons"]))
    return result


@task(name="register")
def register_task(gate_result: dict, cfg: dict) -> str | None:
    """สรุปสถานะ registry + บอก API ให้โหลด champion ใหม่ (ถ้า API เปิดอยู่)"""
    logger = get_run_logger()
    client = registry.get_client(cfg)
    name = registry.model_name(cfg)
    for row in registry.status(client, name):
        logger.info("registry: %s", row)
    champ = registry.get_alias_version(registry.CHAMPION, client, name)
    champ_version = champ.version if champ else None
    logger.info("v%s promoted=%s → champion ปัจจุบัน = v%s",
                gate_result["version"], gate_result["promoted"], champ_version)

    api_url = os.environ.get("API_URL", "http://localhost:8000")
    try:
        req = urllib.request.Request(f"{api_url}/reload", method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info("API reload: %s", resp.read().decode())
    except OSError as err:
        # API ไม่ได้เปิดไม่ใช่ความผิดของ pipeline → เตือนแล้วไปต่อ
        logger.warning("เรียก %s/reload ไม่ได้ (%s) — เปิด API แล้วเรียก /reload เอง", api_url, err)
    return champ_version


@task(name="batch_predict")
def batch_predict_task(cfg: dict) -> str:
    """ใช้ champion พยากรณ์ "พรุ่งนี้" ทุกสินค้า → data/processed/predictions/<date>.csv"""
    from api.model_service import ModelService  # import ตอนใช้ เพราะโหลด mlflow model หนัก

    svc = ModelService.from_registry(cfg)
    if not svc.ready:
        raise RuntimeError(f"โหลด champion ไม่ได้: {svc.error}")
    df = svc.batch_predict(q=cfg["model"]["quantile_default"])
    out = ROOT / "data" / "processed" / "predictions" / f"{df['date'].iloc[0]}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    get_run_logger().info("batch_predict: %d สินค้า วันที่ %s (model v%s) → %s",
                          len(df), df["date"].iloc[0], svc.model_version, out)
    return str(out)


@flow(name="bakery-demand-pipeline", log_prints=True)
def pipeline(data_path: str | None = None) -> dict:
    """DAG หลัก — data_path=None รันเต็ม raw → serving, ระบุไฟล์ = ตรวจไฟล์นั้นแล้วหยุด (โหมดสาธิต)"""
    cfg = load_config()

    if data_path:
        # โหมดสาธิต: ไฟล์ตัวอย่างเล็กเกินจะ train จึงหยุดหลัง validate (ไฟล์เสีย → Failed ที่ validate)
        df = load_file_task(data_path)
        validate_task(df, str(ROOT / cfg["paths"]["samples_meta"]))
        return {"mode": "check", "data_path": data_path, "validated": True}

    daily = ingest_task(cfg)
    checked = validate_task(daily, str(ROOT / cfg["paths"]["meta"]))
    sizes = split_task(checked, cfg)
    train_task()
    gate_result = gate_task(cfg)
    champion = register_task(gate_result, cfg)
    predictions = batch_predict_task(cfg)
    return {"mode": "full", "split": sizes, "gate": gate_result,
            "champion": champion, "predictions": predictions}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prefect pipeline: raw → serving")
    parser.add_argument("--data", help="ตรวจไฟล์ที่ระบุแทน ingest แล้วหยุด (เช่น data/samples/bad_sales.csv)")
    parser.add_argument("--serve", action="store_true", help=f"ตั้งเวลารันทุกคืน (cron '{NIGHTLY_CRON}')")
    args = parser.parse_args(argv)

    if args.serve:
        pipeline.serve(name="nightly", cron=NIGHTLY_CRON)
        return 0
    try:
        result = pipeline(data_path=args.data)
    except pa.errors.SchemaErrors as err:  # flow Failed → exit code ≠ 0 ให้ CI / scheduler รู้
        print(f"[flow] ❌ pipeline หยุดที่ validate: พบ {len(err.failure_cases)} จุดผิด (ไม่ train ต่อ) "
              f"ดู logs/validation_alerts.log", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"[flow] ❌ pipeline หยุด: {type(err).__name__}: {err}", file=sys.stderr)
        return 1
    if result["mode"] == "check":
        print(f"[flow] ✅ {args.data} ผ่าน validate (โหมดตรวจไฟล์ ไม่ train ต่อ)")
    else:
        gate = result["gate"]
        print(f"[flow] ✅ pipeline สำเร็จ: {gate['run_name']} WAPE={gate['wape']:.4f} "
              f"(naive {gate['naive_wape']:.4f}) → v{gate['version']}, champion = v{result['champion']}, "
              f"batch → {result['predictions']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
