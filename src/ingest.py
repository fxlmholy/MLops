"""P2 (M2) — อ่าน csv ดิบ → ทำความสะอาด → aggregate เป็นยอดขายรายวัน × รายสินค้า

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import pandas as pd


def load_raw(path: str) -> pd.DataFrame:
    """TODO(M2): อ่าน csv, แปลง unit_price "0,90 €" -> 0.90, แปลง date"""
    raise NotImplementedError


def to_daily(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """TODO(M2): รวม Quantity เป็น date × article, เติมวันที่ไม่มีขาย = 0, เลือก top-N"""
    raise NotImplementedError


if __name__ == "__main__":
    raise SystemExit("TODO(M2)")
