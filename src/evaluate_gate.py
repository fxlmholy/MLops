"""P4 (M4) — ด่านตรวจก่อนอนุมัติ: ผ่าน gating metric ทุกข้อ → challenger; ชนะ champion → promote

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""


def passes_gate(metrics: dict, naive_wape: float, cfg: dict) -> tuple[bool, list[str]]:
    """คืน (ผ่านหรือไม่, เหตุผลที่ไม่ผ่าน)"""
    reasons = []
    need = naive_wape * (1 - cfg["gate"]["min_improvement_vs_naive"])
    if metrics["wape"] > need:
        reasons.append(f"WAPE {metrics['wape']:.3f} > {need:.3f}")
    if metrics.get("model_size_mb", 0) > cfg["gate"]["max_model_size_mb"]:
        reasons.append("model too large")
    return (not reasons), reasons
