"""P4 (M4) — ด่านตรวจก่อนอนุมัติ: ผ่าน gating metric ทุกข้อ → challenger; ชนะ champion → promote

ขั้นตอน (อ่านผลจาก MLflow run ที่ train.py ของ M3 log ไว้):
    1. หา run ล่าสุดของแต่ละโมเดลใน experiment
    2. baseline = run `seasonal_naive` (WAPE บน validation)
    3. candidate = run ที่มีโมเดล และ WAPE validation ต่ำสุด (หรือระบุเองด้วย --run-id)
    4. ตรวจ gate: WAPE ดีกว่า baseline >= 10%, ขนาดโมเดล < 50 MB  (ค่าจาก configs/config.yaml)
       ไม่ผ่าน → ไม่ลงทะเบียน, exit code 1
    5. ผ่าน → ลงทะเบียนเป็น `challenger`
    6. WAPE ดีกว่า `champion` (หรือยังไม่มี champion) → promote เป็น champion
       ไม่ดีกว่า → ค้างเป็น challenger (champion เดิมยังให้บริการต่อ)

รัน:
    python -m src.evaluate_gate                  # เลือก candidate อัตโนมัติ
    python -m src.evaluate_gate --run-id <id>    # บังคับประเมิน run ที่ระบุ (ใช้สาธิต v2 ที่แย่กว่า)
"""

import argparse
import sys

from mlflow import MlflowClient

from src import registry
from src.config import load_config

BASELINE_RUN = "seasonal_naive"
METRIC = "wape"  # train.py log WAPE ของ validation ชื่อ "wape" (test ใช้ "test_wape")


def passes_gate(metrics: dict, naive_wape: float, cfg: dict) -> tuple[bool, list[str]]:
    """คืน (ผ่านหรือไม่, เหตุผลที่ไม่ผ่าน) — ต้องผ่านทุกข้อ"""
    reasons = []
    gate = cfg["gate"]
    need = naive_wape * (1 - gate["min_improvement_vs_naive"])
    if metrics["wape"] > need:
        reasons.append(f"WAPE {metrics['wape']:.3f} > {need:.3f} (ต้องดีกว่า seasonal-naive "
                       f"{gate['min_improvement_vs_naive']:.0%})")
    if metrics.get("model_size_mb", 0) > gate["max_model_size_mb"]:
        reasons.append(f"model size {metrics['model_size_mb']:.1f} MB > {gate['max_model_size_mb']} MB")
    # p95 latency วัดจาก load test (P5) — ตรวจเมื่อมีค่าส่งมา
    max_p95 = gate.get("max_p95_latency_ms")
    if max_p95 is not None and metrics.get("p95_latency_ms", 0) > max_p95:
        reasons.append(f"p95 latency {metrics['p95_latency_ms']:.0f} ms > {max_p95} ms")
    return (not reasons), reasons


def latest_runs(client: MlflowClient, experiment_name: str) -> dict:
    """run ล่าสุดของแต่ละ run_name (ถ้าเทรนหลายรอบ ใช้รอบล่าสุด)"""
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        raise RuntimeError(f"ไม่พบ experiment '{experiment_name}' — รัน python -m src.train ก่อน")
    runs = client.search_runs([exp.experiment_id], filter_string="attributes.status = 'FINISHED'",
                              order_by=["attributes.start_time DESC"], max_results=200)
    latest = {}
    for run in runs:
        latest.setdefault(run.info.run_name, run)
    return latest


def model_size_mb(client: MlflowClient, run_id: str, path: str = "model") -> float:
    """ขนาดรวมของไฟล์ในโฟลเดอร์ artifact `model` (MB)"""
    total = 0
    for f in client.list_artifacts(run_id, path):
        total += model_size_mb(client, run_id, f.path) * 1024 * 1024 if f.is_dir else (f.file_size or 0)
    return total / (1024 * 1024)


def has_model(client: MlflowClient, run_id: str) -> bool:
    return any(f.path == "model" for f in client.list_artifacts(run_id))


def evaluate(run_id: str | None = None, cfg: dict | None = None) -> dict:
    """ประเมิน candidate ผ่าน gate → register → (อาจ) promote; คืนผลสรุปเป็น dict"""
    cfg = cfg or load_config()
    client = registry.get_client(cfg)
    name = registry.model_name(cfg)
    runs = latest_runs(client, cfg["mlflow"]["experiment"])

    if BASELINE_RUN not in runs:
        raise RuntimeError(f"ไม่พบ run baseline '{BASELINE_RUN}'")
    naive_wape = runs[BASELINE_RUN].data.metrics[METRIC]

    if run_id is None:
        candidates = [r for n, r in runs.items()
                      if n != BASELINE_RUN and METRIC in r.data.metrics and has_model(client, r.info.run_id)]
        if not candidates:
            raise RuntimeError("ไม่มี run ที่มีโมเดลให้ประเมิน")
        cand = min(candidates, key=lambda r: r.data.metrics[METRIC])
    else:
        cand = client.get_run(run_id)
        if not has_model(client, run_id):
            raise RuntimeError(f"run {run_id} ไม่มี artifact 'model' (เช่น seasonal_naive) — ลงทะเบียนไม่ได้")

    metrics = {"wape": cand.data.metrics[METRIC], "model_size_mb": model_size_mb(client, cand.info.run_id)}
    ok, reasons = passes_gate(metrics, naive_wape, cfg)
    result = {"run_name": cand.info.run_name, "run_id": cand.info.run_id, "naive_wape": naive_wape,
              **metrics, "passed_gate": ok, "reasons": reasons, "version": None, "promoted": False}

    print(f"[gate] candidate={cand.info.run_name}  WAPE={metrics['wape']:.4f}  "
          f"naive WAPE={naive_wape:.4f}  size={metrics['model_size_mb']:.2f} MB")
    if not ok:
        print("[gate] ❌ REJECTED — " + "; ".join(reasons))
        return result
    print("[gate] ✅ ผ่าน gating metric ทุกข้อ")

    version = registry.register_challenger(cand.info.run_id, client, name)
    result["version"] = version

    champ = registry.get_alias_version(registry.CHAMPION, client, name)
    champ_wape = client.get_run(champ.run_id).data.metrics.get(METRIC) if champ else None
    result["champion_wape"] = champ_wape
    if champ is None or metrics["wape"] < champ_wape:
        registry.promote(version, client, name)
        result["promoted"] = True
        print(f"[gate] 🏆 v{version} เป็น champion ใหม่")
    else:
        print(f"[gate] v{version} ไม่ชนะ champion v{champ.version} (WAPE {champ_wape:.4f}) "
              "→ ค้างเป็น challenger, champion เดิมให้บริการต่อ")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Model quality gate + registry")
    parser.add_argument("--run-id", help="ประเมิน run ที่ระบุแทนการเลือกอัตโนมัติ")
    args = parser.parse_args(argv)
    result = evaluate(args.run_id)
    return 0 if result["passed_gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
