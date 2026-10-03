"""P2 (M2) — แบ่ง train/val/test ตามเวลา (ห้ามสุ่ม)

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import pandas as pd


def time_split(df: pd.DataFrame, train_end: str, val_end: str):
    """คืน (train, val, test) แบ่งตามคอลัมน์ date"""
    d = pd.to_datetime(df["date"])
    train = df[d <= train_end]
    val = df[(d > train_end) & (d <= val_end)]
    test = df[d > val_end]
    return train, val, test
