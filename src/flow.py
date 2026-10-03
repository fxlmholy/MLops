"""P7 (M2) — Prefect DAG: ingest → validate → split → train → gate → register → batch_predict (คำสั่งเดียว)

ดูรายละเอียดงานและ Definition of Done ใน CLAUDE.md
เมื่อทำเสร็จ: อัปเดต section ของขั้นนี้ใน report.md ใน PR เดียวกัน
"""


def pipeline():
    """TODO(M2): ใช้ @flow / @task ของ Prefect; validate fail → หยุดทั้ง flow"""
    raise NotImplementedError


if __name__ == "__main__":
    pipeline()
