"""P4 (M4) — promote / rollback ด้วย MLflow alias (champion / challenger)

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import sys


def promote(version: int) -> None:
    """TODO(M4): MlflowClient().set_registered_model_alias(name, "champion", version)"""
    raise NotImplementedError


def rollback() -> None:
    """TODO(M4): ย้าย champion กลับไปเวอร์ชันก่อนหน้า"""
    raise NotImplementedError


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"rollback": rollback}.get(cmd, lambda: print("usage: python -m src.registry rollback"))()
