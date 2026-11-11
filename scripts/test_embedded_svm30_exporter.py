#!/usr/bin/env python3
"""Pinned model exporter QA. Does not read serial or flash firmware."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from export_svm30_for_avr import as_c_float,EXPECTED_SHA,EXPECTED_CLASSES
from svm30_embedded_features import FEATURE_ORDER

ROOT=Path(__file__).resolve().parents[1]


def run():
    h=ROOT/"private/embedded_svm30_model.h"
    manifest=ROOT/"private/embedded_svm30_manifest.json"
    assert h.is_file() and manifest.is_file()
    import hashlib
    report=json.loads(manifest.read_text(encoding="utf8"))
    assert report["model_source_sha256"]==EXPECTED_SHA
    assert report["generated_header_sha256"]==hashlib.sha256(h.read_bytes()).hexdigest()
    assert tuple(report["features"])==FEATURE_ORDER
    assert tuple(report["class_order"])==EXPECTED_CLASSES
    assert report["support_vectors_per_class"]==[44,34,47]
    assert report["n_support_vectors"]==125 and report["n_features"]==30
    assert report["uncompressed_flash_vectors_bytes"]==15000
    assert report["uncompressed_flash_dual_coef_bytes"]==1000
    source=h.read_text(encoding="utf8")
    assert "PROGMEM" in source and "kSVectors[3750]" in source
    assert "kDualCoef[250]" in source and "kScale[30]" in source
    assert "kMean[30]" in source and "kNSupport[3]" in source
    assert as_c_float(0)=="0.0f"
    assert as_c_float(12)=="12.0f"
    assert as_c_float(-8)=="-8.0f"
    assert as_c_float(.125)=="0.125f"
    if subprocess.run(["git","check-ignore","-q",
                       "private/embedded_svm30_model.h"],cwd=ROOT).returncode!=0:
        raise AssertionError("PRIVATE_MODEL_HEADER_IS_NOT_GITIGNORED")
    if subprocess.run(["git","check-ignore","-q",
                       "private/svm30_golden_scores_full199.json"],
                      cwd=ROOT).returncode!=0:
        raise AssertionError("PRIVATE_GOLDEN_NOT_GITIGNORED")
    print("EMBEDDED_SVM30_MODEL_EXPORT_AND_PRIVACY_QA_PASS",
          {"private_header_sha256":report["generated_header_sha256"],
           "model_sha256":EXPECTED_SHA,
           "sv":125,"features":30,
           "model_coefficients_in_flash":True,
           "files_excluded_from_public_git":True})


if __name__=="__main__":
    run()
