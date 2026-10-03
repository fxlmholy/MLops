"""P6 (M5) — Evidently data drift (PSI) + concept drift (rolling 7-day WAPE) + เกณฑ์แจ้งเตือน

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""


def check_data_drift(reference, current, threshold: float) -> dict:
    """TODO(M5): Evidently DataDriftPreset / PSI"""
    raise NotImplementedError


def check_concept_drift(wape_7d: float, wape_deploy: float, ratio: float) -> bool:
    """True = เกิด concept drift (ประสิทธิภาพตกเกินเกณฑ์)"""
    return wape_7d > ratio * wape_deploy
