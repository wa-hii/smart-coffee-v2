#!/usr/bin/env python3
"""Export the exact *user-supplied* 30-feature SVC to AVR Flash.

Only explicit --bundle and --out paths. No network, USB, Pi, or flashing.
The generated header contains the complete private SVM and MUST NOT be
committed. Native/AVR consumers use pgm_read_float (no SRAM model copy).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_SHA="d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33"
EXPECTED_CLASSES=("dark","light","medium")
EXPECTED_FEATURE_COUNT=30
EXPECTED_SV_COUNTS=(44,34,47)


def as_c_float(x):
    import numpy as np
    val=float(np.float32(x))
    if not np.isfinite(val):
        raise ValueError("nonfinite_avr_coefficient")
    # float32 values round-trip exactly from scientific notation with 9 digits.
    literal=f"{val:.9g}"
    # '0f' and '12f' are not valid C++ float literals.
    if "." not in literal and "e" not in literal:
        literal += ".0"
    return literal+"f"


def format_array(name,values,ctype="float",per_line=6):
    vals=[as_c_float(x) if ctype=="float" else str(int(x)) for x in values]
    lines=[f"static const {ctype} {name}[{len(vals)}] PROGMEM = {{"]
    for off in range(0,len(vals),per_line):
        lines.append("  "+", ".join(vals[off:off+per_line])+",")
    lines.append("};")
    return "\n".join(lines)


def export(bundle:Path,out:Path,manifest:Path,expected_sha:str=EXPECTED_SHA):
    import numpy as np
    import joblib
    if out.exists() or manifest.exists():
        raise FileExistsError("refuse_overwrite_private_model")
    actual=hashlib.sha256(bundle.read_bytes()).hexdigest()
    if actual!=expected_sha:
        raise ValueError("unapproved_source_model_sha256")
    obj=joblib.load(bundle) # trusted user-supplied / hash-pinned joblib ONLY
    if set(obj)!={"model","scaler","feature_names","feature_indices","classes"}:
        raise ValueError("bundle_schema_unexpected")
    svm=obj["model"];scaler=obj["scaler"]
    names=[str(x) for x in obj["feature_names"]]
    classes=tuple(map(str,svm.classes_))
    if (classes!=EXPECTED_CLASSES or
        tuple(map(str,obj["classes"]))!=classes or
        len(names)!=EXPECTED_FEATURE_COUNT or
        tuple(map(int,svm.n_support_))!=EXPECTED_SV_COUNTS or
        svm.support_vectors_.shape!=(125,30) or
        svm.dual_coef_.shape!=(2,125) or
        svm.intercept_.shape!=(3,) or
        not svm.kernel=="rbf" or svm.C!=1 or
        float(svm._gamma)!=.1 or
        scaler.mean_.shape!=(30,) or scaler.scale_.shape!=(30,)):
        raise ValueError("unapproved_model_or_dimension_change")
    source=Path(__file__).resolve().parents[1]
    from sys import path as pythonpath
    pythonpath.insert(0,str(source/"scripts"))
    from svm30_embedded_features import FEATURE_ORDER
    if tuple(names)!=FEATURE_ORDER:
        raise ValueError("unsupported_feature_order_for_streaming_MCU")
    if (any(not np.isfinite(a).all() for a in
           (svm.support_vectors_,svm.dual_coef_,svm.intercept_,
            scaler.mean_,scaler.scale_)) or
        any(float(x)<=0 for x in scaler.scale_)):
        raise ValueError("invalid_model_parameters")

    body=["// PRIVATE SVM30 model, generated from exact SHA256-pinned user bundle.",
          "// Contains complete training-derived support vectors. DO NOT COMMIT.",
          "#pragma once",
          "#include <stdint.h>",
          "#ifdef __AVR__",
          "#include <avr/pgmspace.h>",
          "#else",
          "#ifndef PROGMEM",
          "#define PROGMEM",
          "#endif",
          "#endif",
          "namespace EmbeddedSvm30Parameters {",
          "static constexpr uint8_t kFeatures = 30;",
          "static constexpr uint8_t kSV = 125;",
          "static constexpr float kGamma = 0.1f;",
          format_array("kNSupport",svm.n_support_,ctype="uint8_t"),
          format_array("kMean",scaler.mean_),
          format_array("kScale",scaler.scale_),
          format_array("kSVectors",svm.support_vectors_.ravel()),
          format_array("kDualCoef",svm.dual_coef_.ravel()),
          format_array("kIntercept",svm.intercept_),
          "}"]
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text("\n".join(body)+"\n",encoding="utf8")
    export_sha=hashlib.sha256(out.read_bytes()).hexdigest()
    manifest.write_text(json.dumps({
        "model_source_sha256":actual,"generated_header_sha256":export_sha,
        "private_generated_header":str(out.name),
        "features":names,"class_order":list(classes),
        "support_vectors_per_class":list(EXPECTED_SV_COUNTS),
        "n_support_vectors":125,"n_features":30,"kernel":"rbf",
        "gamma":.1,"C":1,"avr_float_bytes":4,
        "uncompressed_flash_vectors_bytes":125*30*4,
        "uncompressed_flash_dual_coef_bytes":2*125*4,
        "model_quantization":"IEEE 754 float32",
        "not_production_validated":True,
        "no_external_pi_required_for_inference":True,
        "source_model_not_retrained":True
    },indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print(json.dumps({"status":"AVR_SVM30_PRIVATE_HEADER_GENERATED",
        "source_sha256":actual,"header_sha256":export_sha,
        "model_sv":125,"model_features":30,
        "header_bytes":out.stat().st_size},ensure_ascii=False))


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--bundle",type=Path,required=True)
    a.add_argument("--out",type=Path,default=Path("private/embedded_svm30_model.h"))
    a.add_argument("--manifest",type=Path,default=Path("private/embedded_svm30_manifest.json"))
    args=a.parse_args()
    export(args.bundle,args.out,args.manifest)


if __name__=="__main__":
    main()
