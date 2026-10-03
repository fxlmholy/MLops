"""P6 (M5) — สร้างข้อมูลจำลอง Data Drift (P(X) เปลี่ยน) และ Concept Drift (P(y|X) เปลี่ยน)

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""


def make_data_drift(df, factor: float = 1.5):
    """TODO(M5): เลื่อน distribution ของ feature / สัดส่วนสินค้า"""
    raise NotImplementedError


def make_concept_drift(df, factor: float = 0.6):
    """TODO(M5): feature เหมือนเดิม แต่ยอดขายจริง × factor (เช่น คู่แข่งเปิดร้าน)"""
    raise NotImplementedError
