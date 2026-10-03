"""P2 (M2) — Pandera schema + ตรวจ anomaly → ข้อมูลเสียต้อง raise และ exit code != 0

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import sys

import pandas as pd


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """TODO(M2): schema = ชนิดข้อมูล, qty >= 0, article ใน known_items, date ไม่ซ้ำ/ไม่หาย"""
    raise NotImplementedError


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    raise SystemExit(f"TODO(M2): validate {path}")
