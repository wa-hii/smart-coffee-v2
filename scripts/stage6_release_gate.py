"""Tahap 6 (persiapan): fail-closed promotion gate, TIDAK mengaktifkan model.

No production model creation/selection. Default N/A until independent
prospective multi-specimen/unknown testing is actually provided.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE5 = ROOT / "results/stage5_validation_v1/summary.json"
EXTERNAL = ROOT / "results/external_coffee_enose_v1/summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(stage5_path: Path = STAGE5,
             external_path: Path = EXTERNAL) -> dict:
    local = json.loads(stage5_path.read_text(encoding="utf-8"))
    ext = json.loads(external_path.read_text(encoding="utf-8"))
    if local.get("status") != "EXPLORATORY_STAGE5_NO_GO_PROSPECTIVE_UNAVAILABLE":
        raise ValueError("Unknown stage 5 provenance/status; refuse promotion")
    if (local.get("coffee_candidate_files") != 83 or
            local.get("clean_air_known_files") != 6 or
            local.get("clean_air_strict_valid") != 5 or
            local.get("models_promoted") != 0 or
            local.get("prospective_external_batch_tested") is not False):
        raise ValueError("Stage 5 status unexpected; refuse promotion")
    if (ext.get("status") !=
            "REAL_EXTERNAL_DATA_VERIFIED_BENCHMARK_EXPLORATORY_ONLY" or
            ext.get("external_data_added_to_local_roast_training") is not False or
            ext.get("local_model_approval") != "NO_GO" or
            ext.get("coffee_pow4_included_identically_in_aroma7") is not True):
        raise ValueError("External provenance/status unexpected; refuse promotion")
    return {
        "status": "NO_GO_PENDING_LOCAL_VALIDATION",
        "model_promotion_allowed": False,
        "runtime_ai_test_result": "N/A",
        "runtime_reason": "Model belum tervalidasi; tidak boleh memaksa prediksi kopi",
        "sensor_contract": "10 MQ/TGS ADC+SHT30, five 25s/5s cycles",
        "external_sensor_contract": "BME688 gas resistance at 10 heater steps",
        "external_transfer_training_allowed": False,
        "local_stage5_summary_sha256": sha256(stage5_path),
        "external_evaluation_summary_sha256": sha256(external_path),
        "unresolved_requirements": [
            "Physical specimen_id, origin and roast label independently audited",
            "Separate prospective local-device coffee and ambient-air sessions",
            "Coffee presence vs air vs other VOC defined and tested on real hardware",
            "Unknown-origin coffee blind prospective trials",
            "Threshold pre-specified on calibration set, final sealed holdout",
            "Calibration, uncertainty, drift/warm-up and safety validated",
            "Independent QA plus operator sign-off for Raspberry Pi deployment",
        ],
        "warning": "High external BME688 dataset metrics are NOT "
                   "transfer evidence to the 10-channel ADC E-Nose.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = evaluate()
    if args.output.exists():
        raise FileExistsError("Do not overwrite an existing stage6 decision")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("STAGE6_FAIL_CLOSED_GATE_PASS")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
