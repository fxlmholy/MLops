"""P2 (M2) — แบ่ง train/val/test ตามเวลา (ห้ามสุ่ม)

เหตุผล: โจทย์คือพยากรณ์ "อนาคต" ถ้าสุ่มแบ่ง โมเดลจะได้เห็นยอดของวันหลังจากวันที่ทำนาย (leakage)
แล้วได้คะแนนดีเกินจริง จึงแบ่งด้วยวันที่ใน configs/config.yaml:
    train: date <= train_end · val: train_end < date <= val_end · test: date > val_end

รัน:  python -m src.split     (พิมพ์ช่วงวันที่และจำนวนแถวของแต่ละชุด)
"""

import pandas as pd

from src.config import ROOT, load_config


def time_split(df: pd.DataFrame, train_end: str, val_end: str):
    """คืน (train, val, test) แบ่งตามคอลัมน์ date"""
    d = pd.to_datetime(df["date"])
    train = df[d <= train_end]
    val = df[(d > train_end) & (d <= val_end)]
    test = df[d > val_end]
    return train, val, test


def split_from_config(df: pd.DataFrame, cfg: dict | None = None):
    """แบ่งด้วยวันที่ใน config และตรวจว่าไม่มีชุดไหนว่าง (วันที่ใน config ไม่ตรงกับข้อมูล)"""
    cfg = cfg or load_config()
    parts = time_split(df, cfg["split"]["train_end"], cfg["split"]["val_end"])
    for name, part in zip(["train", "val", "test"], parts, strict=True):
        if part.empty:
            raise ValueError(f"ชุด {name} ว่าง — ตรวจ split.train_end / split.val_end ใน config")
    return parts


if __name__ == "__main__":
    data = pd.read_parquet(ROOT / load_config()["paths"]["processed"])
    for name, part in zip(["train", "val", "test"], split_from_config(data), strict=True):
        print(f"{name:5s}: {part['date'].min()} → {part['date'].max()}  ({len(part)} แถว)")
