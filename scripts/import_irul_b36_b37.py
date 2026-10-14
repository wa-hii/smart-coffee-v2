"""Copy B36/B37 CSV bytes from fetched origin/irul to a separate raw namespace.

Do not overwrite source files, and never promote these to ML automatically.
This is a one-off evidence-preserving import, without touching hardware.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"^data/(?:BASELINE|[DML]-[A-Z0-9]+)_B(?:36|37)\.csv$")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "data/raw/irul_B36_B37")
    args = parser.parse_args()
    dest = args.destination.resolve()
    raw = (ROOT / "data/raw").resolve()
    if not raw in dest.parents or dest.exists():
        raise ValueError("Require fresh namespaced import under data/raw")
    source_commit = git("rev-parse", "origin/irul").decode().strip()
    names = [name for name in git("ls-tree", "-r", "--name-only", "origin/irul", "--", "data")
             .decode().splitlines() if PATTERN.fullmatch(name)]
    if not names or len(set(names)) != len(names):
        raise ValueError("No valid source files or duplicated paths")

    rows = []
    pending = []
    for name in names:
        data = git("show", f"{source_commit}:{name}")
        if not data.startswith(b"timestamp,sample_id,roast_level,origin,batch_id,"):
            raise ValueError(f"Unexpected raw CSV schema: {name}")
        filename = Path(name).name
        local = raw / filename
        digest = hashlib.sha256(data).hexdigest()
        exists = local.is_file()
        local_hash = hashlib.sha256(local.read_bytes()).hexdigest() if exists else ""
        rows.append({
            "source_branch": "origin/irul", "source_commit": source_commit,
            "source_path": name, "import_relative_path": f"data/raw/irul_B36_B37/{filename}",
            "sha256": digest, "byte_count": len(data),
            "existing_root_raw_collision": exists,
            "existing_root_raw_sha256": local_hash,
            "same_as_existing_root_raw": bool(exists and local_hash == digest),
            "ml_status": "HOLD_PROVENANCE_UNVERIFIED_NOT_BLIND",
        })
        pending.append((filename, data))

    dest.mkdir(parents=True)
    for filename, data in pending:
        (dest / filename).write_bytes(data)
        if hashlib.sha256((dest / filename).read_bytes()).hexdigest() != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f"Import checksum mismatch: {filename}")
    summary = {
        "status": "IMPORTED_UNMODIFIED_RAW_HOLD_NO_MODEL_TRAINING",
        "source_commit": source_commit,
        "source_branch": "origin/irul",
        "files_imported": len(rows),
        "batch36": sum("_B36.csv" in x["source_path"] for x in rows),
        "batch37": sum("_B37.csv" in x["source_path"] for x in rows),
        "root_raw_name_collisions_preserved": sum(x["existing_root_raw_collision"] for x in rows),
        "origin_roast_physical_provenance_verified": False,
        "blind_test_independence_verified": False,
        "model_promotion_allowed": False,
    }
    manifest = ROOT / "data/analysis/irul_B36_B37_import_manifest.csv"
    if manifest.exists():
        raise FileExistsError("Refusing to overwrite provenance manifest")
    with manifest.open("w", newline="", encoding="utf-8") as fd:
        writer = csv.DictWriter(fd, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = ROOT / "data/analysis/irul_B36_B37_import_summary.json"
    if report.exists():
        raise FileExistsError("Refusing to overwrite import summary")
    report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
