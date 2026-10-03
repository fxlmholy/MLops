"""P3 (M3) — เทรน + log MLflow ครบ 6 อย่าง: code ver, data ver, params, metrics, artifacts, environment

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""

import hashlib
import subprocess


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def wape(y_true, y_pred) -> float:
    """Weighted Absolute Percentage Error = sum|y - ŷ| / sum|y|"""
    import numpy as np

    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    denom = np.abs(y_true).sum()
    return float(np.abs(y_true - y_pred).sum() / denom) if denom else 0.0


def main():
    """TODO(M3): run 1 seasonal-naive, 2 linear, 3 lgbm default, 4 lgbm tuned"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
