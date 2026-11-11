#!/usr/bin/env python3
"""B2/B3 negative read-only replay tests against native 900-sample CLI."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from svm30_roast_model import ADC_COLUMNS,InvalidCapture
from test_embedded_svm30_parity import strict_source,native_input


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary",type=Path,required=True)
    args=parser.parse_args()
    binary=args.binary.resolve()
    path=ROOT/"data/dataset sorting/c/kept/D-CAT_B80.csv"
    rows=strict_source(path)
    raw=native_input(rows).splitlines()
    assert len(raw)==900
    mutations={
      "five_cycles":raw[:150],
      "missing_last":raw[:-1],
      "missing_mid":raw[:72]+raw[73:],
      "duplicate_mid":raw[:72]+raw[72:73]+raw[72:],
      "extra_sample":raw+[raw[-1]],
      "wrong_phase":raw[:30]+[raw[30].replace(" 0 "," 1 ",1)]+raw[31:],
      "wrong_index":raw[:25]+[" ".join(
          [raw[25].split()[0],raw[25].split()[1],"2",*raw[25].split()[3:]]
          )]+raw[26:],
      "wrong_cycle":raw[:30]+[" ".join(
          ["99",*raw[30].split()[1:]]
          )]+raw[31:],
      "invalid_adc":raw[:50]+[" ".join(
          [*raw[50].split()[:3],"40000",*raw[50].split()[4:]]
          )]+raw[51:],
      "nan_adc":raw[:50]+[" ".join(
          [*raw[50].split()[:3],"nan",*raw[50].split()[4:]]
          )]+raw[51:],
    }
    ok=subprocess.run([str(binary)],input="\n".join(raw)+"\n",
                      text=True,capture_output=True,timeout=25)
    assert ok.returncode==0 and '"roast":' in ok.stdout
    for name,rows_modified in mutations.items():
        proc=subprocess.run([str(binary)],
                            input="\n".join(rows_modified)+"\n",
                            text=True,capture_output=True,timeout=25)
        if proc.returncode==0:
            raise AssertionError("MALFORMED_SESSION_WAS_ACCEPTED:"+name)
        if '"roast":' in proc.stdout:
            raise AssertionError("MODEL_GUESSED_FOR_BROKEN_SESSION:"+name)
    print("EMBEDDED_SVM30_NEGATIVE_INPUT_QA_PASS",
          {"bad_sessions_rejected":len(mutations),
           "good_900_sample_session_accepted":True,
           "uart_opened":False,"hardware_touched":False})


if __name__=="__main__":
    main()
