#!/usr/bin/env python3
"""Read-only integrity check for user-provided RF500 binary staged on Pi.

Does NOT call joblib.load or use USB. Suitable for SSH stdin python3 -B -.
"""
from __future__ import annotations

import hashlib
from importlib import metadata
import json
from pathlib import Path
import sys

STAGE=Path.home()/"smart-coffee-stage7"/"rf30_staging"
sys.path.insert(0,str(STAGE))
from roast_rf30_pi_inference import verify_artifact,EXPECTED_SHA

model=STAGE/"final_model.joblib"
meta=STAGE/"final_model_info.json"
verified=verify_artifact(model,meta)
assert verified["sha256"]==EXPECTED_SHA
assert verified["n_estimators"]==500
assert verified["features"]==[
    "tgs822_max_mean","tgs822_purging_mean_mean","mq8_max_mean"
]
versions={}
for package in ("scikit-learn","numpy","scipy","joblib","pyserial"):
    try:
        versions[package]=metadata.version(package)
    except metadata.PackageNotFoundError:
        versions[package]="NOT_INSTALLED"
print(json.dumps({
    "status":"RF30_PI_MODEL_HASH_METADATA_PASS_NO_DESERIALIZATION",
    "model_sha256":verified["sha256"],"model_bytes":model.stat().st_size,
    "python":sys.version.split()[0],"packages":versions,
    "serial_opened":False,"model_loaded":False,"origin_ground_truth_used":False,
},ensure_ascii=True))
