#!/usr/bin/env python3
"""plot_collecting.py

Plot ADC sensor values from a collected CSV (phase=collecting by default).
Saves an overlay plot and individual sensor plots into data/plots/.

Usage:
  python scripts/plot_collecting.py --file ../data/light_20260810_160508.csv --phase collecting
"""
import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
try:
    import seaborn as sns
    sns.set(style='darkgrid')
except Exception:
    pass


def main():
    p = argparse.ArgumentParser(description='Plot collecting data CSV')
    p.add_argument('--file', '-f', default=os.path.join('..','data','light_20260810_160508.csv'))
    p.add_argument('--phase', '-p', default='collecting', help='phase to filter: collecting or purging')
    p.add_argument('--sensors', '-s', nargs='*', default=None, help='list of sensor columns to plot (default: autodetect adc_*)')
    args = p.parse_args()

    fp = os.path.abspath(args.file)
    if not os.path.exists(fp):
        print(f"File not found: {fp}")
        return

    df = pd.read_csv(fp)
    # Filter phase if column exists
    if 'phase' in df.columns and args.phase:
        df = df[df['phase'] == args.phase]

    # Detect timestamp or use index/sample_idx
    if 'timestamp' in df.columns:
        try:
            df['__ts'] = pd.to_datetime(df['timestamp'])
        except Exception:
            df['__ts'] = pd.to_datetime(df['timestamp'], errors='coerce')
            df['__ts'] = df['__ts'].fillna(pd.RangeIndex(len(df)))
    elif 'sample_idx' in df.columns:
        df['__ts'] = df['sample_idx']
    else:
        df['__ts'] = pd.RangeIndex(len(df))

    # Sensor columns
    if args.sensors:
        sensors = [s for s in args.sensors if s in df.columns]
    else:
        sensors = [c for c in df.columns if c.startswith('adc_')]

    if not sensors:
        print('No sensor columns found (look for columns starting with "adc_").')
        return

    outdir = os.path.join(os.path.dirname(fp), 'plots')
    os.makedirs(outdir, exist_ok=True)

    # Overlay plot
    plt.figure(figsize=(12, 6))
    for c in sensors:
        plt.plot(df['__ts'], df[c], label=c)
    plt.legend(loc='upper right')
    plt.xlabel('time')
    plt.ylabel('ADC value')
    plt.title(f"Sensors overlay ({os.path.basename(fp)} - {args.phase})")
    plt.tight_layout()
    outpath = os.path.join(outdir, os.path.basename(fp).replace('.csv', f'_{args.phase}_overlay.png'))
    plt.savefig(outpath, dpi=150)
    plt.close()
    print(f"Saved overlay plot: {outpath}")

    # Per-sensor plots (compact)
    for c in sensors:
        plt.figure(figsize=(10, 3))
        plt.plot(df['__ts'], df[c])
        plt.xlabel('time')
        plt.ylabel('ADC')
        plt.title(f"{c} ({args.phase})")
        plt.tight_layout()
        path_c = os.path.join(outdir, os.path.basename(fp).replace('.csv', f'_{args.phase}_{c}.png'))
        plt.savefig(path_c, dpi=150)
        plt.close()
        print(f"Saved: {path_c}")

    print('\nDone.')


if __name__ == '__main__':
    main()
