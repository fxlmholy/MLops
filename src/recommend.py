"""P5 (M4) — Newsvendor: แปลงยอดขายที่คาดการณ์ → จำนวนที่ควรเตรียม

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import math


def critical_ratio(unit_price: float, unit_cost: float) -> float:
    """q = (ราคาขาย - ต้นทุน) / ราคาขาย  = Cu / (Cu + Co)"""
    if unit_price <= 0 or unit_cost < 0 or unit_cost > unit_price:
        raise ValueError("ต้องมี 0 <= unit_cost <= unit_price และ unit_price > 0")
    return (unit_price - unit_cost) / unit_price


def recommended_qty(forecast_q: float, on_hand: int = 0) -> int:
    """จำนวนที่ควรเตรียม = ceil(F_q) - ของที่มีอยู่ (ไม่ติดลบ)"""
    return max(0, math.ceil(forecast_q) - on_hand)
