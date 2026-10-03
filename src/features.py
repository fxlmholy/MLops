"""P3 (M3) — build_features() — ใช้ร่วมกันทั้งตอน train และ serve เพื่อกัน Training-Serving Skew

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import pandas as pd


def build_features(history: pd.DataFrame, lags=(1, 7, 14), windows=(7, 28)) -> pd.DataFrame:
    """TODO(M3): lag, rolling mean/std (shift 1 กัน leakage), day_of_week, month, is_weekend, is_holiday

    ห้ามเขียน logic แปลงข้อมูลซ้ำที่อื่น — API ต้อง import ฟังก์ชันนี้
    """
    raise NotImplementedError
