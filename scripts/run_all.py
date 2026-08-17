"""run_all.py
Run full pipeline: extract features -> train Random Forest -> export C header

Usage:
  python scripts/run_all.py --export-header

This script calls the existing scripts in this repo using the current Python
interpreter. It expects:
 - scripts/1_ekstraksi_fitur.py
 - scripts/train_rf_simple.py

It will produce `data/dataset_fitur.csv`, `models/rf_model.joblib` and if
`--export-header` is passed and `micromlgen` is installed, `include/model_rf.h`.
"""
import argparse
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))

def call(script, args=None):
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)]
    if args:
        cmd += args
    print('\n>> Running:', ' '.join(cmd))
    res = subprocess.run(cmd, cwd=ROOT_DIR)
    if res.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)} (exit {res.returncode})")


def main():
    p = argparse.ArgumentParser(description='Run full extract+train+export pipeline')
    p.add_argument('--export-header', action='store_true', help='Ask train script to export include/model_rf.h')
    args = p.parse_args()

    # 1) Extract features
    call('1_ekstraksi_fitur.py')

    # 2) Train RF and save model
    train_args = ['--file', os.path.join('..','data','dataset_fitur.csv')]
    if args.export_header:
        train_args.append('--export-header')
    call('train_rf_simple.py', train_args)

    print('\n=== Pipeline complete ===')
    print(' - dataset: data/dataset_fitur.csv')
    print(' - model:   models/rf_model.joblib')
    if args.export_header:
        print(' - header:  include/model_rf.h (if micromlgen installed)')

if __name__ == '__main__':
    main()
