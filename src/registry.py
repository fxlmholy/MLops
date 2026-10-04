"""P4 (M4) — จัดการ MLflow Model Registry ด้วย alias `champion` / `challenger`

สถานะของแต่ละเวอร์ชันเก็บเป็น tag `status` บน model version:
    challenger = ผ่าน gate แล้ว รอเทียบกับ champion
    champion   = เวอร์ชันที่ API ใช้งานจริง
    archived   = เคยเป็น champion แต่ถูกแทนที่ / ถูก rollback ออก

ประวัติ champion เก็บเป็น tag `champion_history` (JSON list) บน registered model
→ rollback = ย้าย alias `champion` กลับไปเวอร์ชันก่อนหน้าในประวัติ

รัน:
    python -m src.registry status
    python -m src.registry promote <version>
    python -m src.registry rollback
"""

import json
import os
import sys

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from src.config import load_config

CHAMPION = "champion"
CHALLENGER = "challenger"
HISTORY_TAG = "champion_history"


def tracking_uri(cfg: dict | None = None) -> str:
    """env MLFLOW_TRACKING_URI (ใน docker) มาก่อน แล้วค่อยใช้ค่าใน config"""
    cfg = cfg or load_config()
    return os.environ.get("MLFLOW_TRACKING_URI", cfg["mlflow"]["tracking_uri"])


def get_client(cfg: dict | None = None) -> MlflowClient:
    uri = tracking_uri(cfg)
    # ตั้งค่า global ด้วย: artifact แบบ mlflow-artifacts:/ อ้างอิง tracking URI ตัวนี้ตอนดาวน์โหลด/list
    mlflow.set_tracking_uri(uri)
    return MlflowClient(tracking_uri=uri)


def model_name(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    return cfg["mlflow"]["model_name"]


def _history(client: MlflowClient, name: str) -> list[str]:
    tags = client.get_registered_model(name).tags
    return json.loads(tags.get(HISTORY_TAG, "[]"))


def _set_history(client: MlflowClient, name: str, history: list[str]) -> None:
    client.set_registered_model_tag(name, HISTORY_TAG, json.dumps(history))


def get_alias_version(alias: str, client: MlflowClient | None = None, name: str | None = None):
    """คืน ModelVersion ของ alias นั้น หรือ None ถ้ายังไม่มี"""
    client = client or get_client()
    name = name or model_name()
    try:
        return client.get_model_version_by_alias(name, alias)
    except MlflowException:
        return None


def register_challenger(run_id: str, client: MlflowClient | None = None, name: str | None = None) -> str:
    """ลงทะเบียนโมเดลจาก run → เวอร์ชันใหม่ + alias `challenger` + tag status=challenger"""
    client = client or get_client()
    name = name or model_name()
    try:
        client.get_registered_model(name)
    except MlflowException:
        client.create_registered_model(name, description="Bakery daily demand forecast (CP413008)")

    run = client.get_run(run_id)
    mv = client.create_model_version(name, source=f"{run.info.artifact_uri}/model", run_id=run_id)
    client.set_model_version_tag(name, mv.version, "status", CHALLENGER)
    client.set_model_version_tag(name, mv.version, "run_name", run.info.run_name or "")
    client.set_registered_model_alias(name, CHALLENGER, mv.version)
    print(f"[registry] {name} v{mv.version} ← run {run.info.run_name} ({run_id[:8]}) = challenger")
    return str(mv.version)


def promote(version, client: MlflowClient | None = None, name: str | None = None) -> None:
    """ย้าย alias `champion` มาที่ version นี้ และ archive champion ตัวเดิม"""
    client = client or get_client()
    name = name or model_name()
    version = str(version)
    client.get_model_version(name, version)  # ถ้าไม่มีเวอร์ชันนี้จะ raise ทันที

    old = get_alias_version(CHAMPION, client, name)
    if old is not None and str(old.version) == version:
        print(f"[registry] v{version} เป็น champion อยู่แล้ว")
        return
    if old is not None:
        client.set_model_version_tag(name, old.version, "status", "archived")

    client.set_registered_model_alias(name, CHAMPION, version)
    client.set_model_version_tag(name, version, "status", CHAMPION)
    # challenger ที่ถูก promote แล้วไม่ต้องค้าง alias challenger ไว้
    challenger = get_alias_version(CHALLENGER, client, name)
    if challenger is not None and str(challenger.version) == version:
        client.delete_registered_model_alias(name, CHALLENGER)

    history = _history(client, name) + [version]
    _set_history(client, name, history)
    print(f"[registry] champion: v{old.version if old else '-'} → v{version}")


def rollback(client: MlflowClient | None = None, name: str | None = None) -> str:
    """ย้าย `champion` กลับไปเวอร์ชันก่อนหน้าในประวัติ (ตัวปัจจุบันกลายเป็น archived)"""
    client = client or get_client()
    name = name or model_name()
    history = _history(client, name)
    if len(history) < 2:
        raise RuntimeError("ไม่มีเวอร์ชันก่อนหน้าให้ rollback (ต้องเคย promote อย่างน้อย 2 ครั้ง)")

    current, previous = history[-1], history[-2]
    client.set_registered_model_alias(name, CHAMPION, previous)
    client.set_model_version_tag(name, previous, "status", CHAMPION)
    client.set_model_version_tag(name, current, "status", "archived")
    client.set_model_version_tag(name, current, "rolled_back", "true")
    _set_history(client, name, history[:-1])
    print(f"[registry] rollback champion: v{current} → v{previous}  (เรียก POST /reload ที่ API เพื่อโหลดใหม่)")
    return previous


def status(client: MlflowClient | None = None, name: str | None = None) -> list[dict]:
    """แสดงทุกเวอร์ชันพร้อม alias และ status"""
    client = client or get_client()
    name = name or model_name()
    rows = []
    for mv in sorted(client.search_model_versions(f"name='{name}'"), key=lambda m: int(m.version)):
        rows.append({
            "version": mv.version,
            "aliases": ",".join(mv.aliases),
            "status": mv.tags.get("status", ""),
            "run_name": mv.tags.get("run_name", ""),
        })
    for r in rows:
        print(f"v{r['version']:<3} {r['status']:<11} aliases=[{r['aliases']}]  run={r['run_name']}")
    return rows


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "rollback":
        rollback()
    elif cmd == "promote" and len(argv) == 2:
        promote(argv[1])
    elif cmd == "status":
        status()
    else:
        print("usage: python -m src.registry [status | promote <version> | rollback]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
