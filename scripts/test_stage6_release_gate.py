"""Stage6 cannot silently promote model just because external scores improve."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from stage6_release_gate import evaluate, EXTERNAL, STAGE5


def main() -> int:
    result = evaluate()
    assert result["status"] == "NO_GO_PENDING_LOCAL_VALIDATION"
    assert result["runtime_ai_test_result"] == "N/A"
    assert result["model_promotion_allowed"] is False
    assert result["external_transfer_training_allowed"] is False
    assert len(result["unresolved_requirements"]) >= 5
    with TemporaryDirectory() as td:
        root = Path(td)
        stage5 = json.loads(STAGE5.read_text())
        external = json.loads(EXTERNAL.read_text())
        # Try to impersonate a complete stage5 validation without evidence.
        stage5["models_promoted"] = 1
        file = root / "stage5.json"
        file.write_text(json.dumps(stage5))
        try:
            evaluate(file, EXTERNAL)
        except ValueError as err:
            assert "Stage 5 status" in str(err)
        else:
            raise AssertionError("Must refuse unexpected promoted local model")
        external["external_data_added_to_local_roast_training"] = True
        other = root / "external.json"
        other.write_text(json.dumps(external))
        try:
            evaluate(STAGE5, other)
        except ValueError as err:
            assert "External provenance" in str(err)
        else:
            raise AssertionError("Must refuse falsely merged external dataset")
    print("STAGE6_RELEASE_GATE_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
