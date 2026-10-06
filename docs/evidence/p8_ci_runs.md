# P8 — หลักฐาน GitHub Actions (PASS / FAIL)

ตัวเลข WAPE ด้านล่างได้จากการรันขั้นตอนเดียวกับ job model-gate ในเครื่อง (seed 42 + version ที่ pin ไว้ → ผลเหมือน CI)
log ฉบับเต็มเปิดได้จากลิงก์ run (แท็บ model-gate → "Model quality gate" และ Job summary)

## ✅ PASS — PR #18 `feature/p8-cicd`
| Job | ผล |
|---|---|
| code-quality (ruff + pytest) | ✅ success |
| data-validation (good ผ่าน / bad ถูกจับ) | ✅ success |
| model-gate | ✅ success — `lightgbm_default WAPE=0.1062 naive WAPE=0.1293` → ดีกว่า 17.9% ≥ 10% → v1 champion |
| docker (build image) | ✅ success |

- https://github.com/fxlmholy/MLops/actions/runs/37453026100
- https://github.com/fxlmholy/MLops/actions/runs/37454699001 (หลังแก้ pipefail)

## ❌ FAIL 1 — PR #19 แก้เกณฑ์ gate เป็น 50% (`configs/config.yaml`)
| Job | ผล |
|---|---|
| code-quality | ❌ failure — `tests/test_registry_gate.py::test_passes_gate_rules`, `::test_gate_promote_reject_and_rollback` |
| data-validation / model-gate / docker | ⏭ skipped (job ก่อนหน้าล้ม) |

- https://github.com/fxlmholy/MLops/actions/runs/37453032360

## ❌ FAIL 2 — PR #19 ข้อมูลที่ seasonal-naive ดีที่สุด (โมเดลชนะ rule ไม่ถึง 10%)
| Job | ผล |
|---|---|
| code-quality | ✅ success |
| data-validation | ✅ success |
| model-gate | ❌ failure ที่ step "Model quality gate" — `[gate] ❌ REJECTED — WAPE 0.083 > 0.074 (ต้องดีกว่า seasonal-naive 10%)` → ไม่ลงทะเบียนโมเดล |
| docker | ✅ success |

- https://github.com/fxlmholy/MLops/actions/runs/37454700982

## หมายเหตุ: run ที่ "ควรแดงแต่เขียว" (บั๊กที่ CI demo ช่วยหาเจอ)
- https://github.com/fxlmholy/MLops/actions/runs/37454106251 — gate REJECT แต่ step ผ่าน เพราะ `| tee` กลืน exit code
- แก้ด้วย `shell: bash` (pipefail) ใน commit `ci: keep evaluate_gate exit code when piping to tee`
