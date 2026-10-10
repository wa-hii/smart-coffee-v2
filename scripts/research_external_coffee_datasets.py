"""Unduh dataset riil CoffeePow-4/Aroma-7 dengan MD5 publisher; no synthetic data.

Data eksternal TIDAK dikonversi menjadi 10-kanal ADC ATmega, tidak
dicampurkan ke dataset roasting, dan tidak ditaruh ke data/raw.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "CoffeePow-4": {
        "url": "https://zenodo.org/records/15425922/files/CoffeePow-4.csv?download=1",
        "doi": "10.5281/zenodo.15425922",
        "md5": "81d373ba934046490862e3964ca77392",
        "filename": "CoffeePow-4.csv",
    },
    "Aroma-7": {
        "url": "https://zenodo.org/records/15425922/files/Aroma-7.csv?download=1",
        "doi": "10.5281/zenodo.15425922",
        "md5": "94562d5bb44d7ee7d28100dd00367975",
        "filename": "Aroma-7.csv",
    },
}


def verify_bytes(content: bytes, expected_md5: str) -> str:
    if hashlib.md5(content).hexdigest() != expected_md5:
        raise ValueError("External dataset checksum mismatch; do not use")
    if not content.startswith(b"Resistance Gassensor,label"):
        raise ValueError("Unexpected external sensor CSV header")
    return hashlib.sha256(content).hexdigest()


def download_dataset(name: str, folder: Path, *, timeout: int = 35) -> dict:
    spec = DATASETS[name]
    if folder.resolve() == (ROOT / "data/raw").resolve() or (
        (ROOT / "data/raw").resolve() in folder.resolve().parents
    ):
        raise ValueError("External data may not enter project sensor raw folder")
    target = folder / spec["filename"]
    if target.exists():
        data = target.read_bytes()
    else:
        response = requests.get(
            spec["url"], timeout=timeout,
            headers={"User-Agent": "CoffeeENoseResearchDatasetAudit/1.0"},
        )
        response.raise_for_status()
        data = response.content
    digest = verify_bytes(data, spec["md5"])
    if not target.exists():
        folder.mkdir(parents=True, exist_ok=True)
        # No overwrite of previously existing bytes.
        with target.open("xb") as out:
            out.write(data)
    return {
        "name": name, "file": spec["filename"], "url": spec["url"],
        "doi": spec["doi"], "md5_verified": spec["md5"],
        "sha256": digest, "bytes": len(data),
        "local_path": str(target),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path,
                   default=ROOT / "data/external/zenodo_15425922")
    args = p.parse_args()
    records = [download_dataset(name, args.output_dir) for name in DATASETS]
    print("EXTERNAL_DATA_REAL_SHA256_VERIFIED")
    print(json.dumps(records, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
