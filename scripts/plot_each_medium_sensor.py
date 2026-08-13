import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

base_dir = Path(__file__).resolve().parent.parent
csv_path = base_dir / "data" / "medium_20260811_170159.csv"
out_dir = base_dir / "data" / "plots" / "medium_per_sensor"
out_dir.mkdir(parents=True, exist_ok=True)

# Baca data
try:
    df = pd.read_csv(csv_path)
except FileNotFoundError:
    raise FileNotFoundError(f"File tidak ditemukan: {csv_path}")

# Ambil fase collecting
if "phase" in df.columns:
    df = df[df["phase"] == "collecting"].copy()

# Kolom X yang umum dipakai
x_col = "sample_idx" if "sample_idx" in df.columns else "timestamp"

# Kolom sensor yang ada di file
sensor_cols = [
    "adc_tgs822",
    "adc_mq135",
    "adc_mq9",
    "adc_tgs2611",
    "adc_tgs2620",
    "adc_tgs2600",
    "adc_tgs2602",
    "adc_mq8",
    "adc_tgs813",
    "adc_tgs816",
]

sensor_cols = [c for c in sensor_cols if c in df.columns]

for sensor in sensor_cols:
    fig, ax = plt.subplots(figsize=(12, 4))
    series = pd.to_numeric(df[sensor], errors="coerce")
    x = pd.to_numeric(df[x_col], errors="coerce")
    valid = series.notna() & x.notna()
    ax.plot(x[valid], series[valid], color="tab:blue", linewidth=1.8)
    ax.set_title(f"Medium - {sensor}")
    ax.set_xlabel(x_col)
    ax.set_ylabel("ADC")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    filename = f"medium_{sensor}.png"
    fig.savefig(out_dir / filename, dpi=180)
    plt.close(fig)
    print(f"Saved: {out_dir / filename}")

print(f"Total sensor plotted: {len(sensor_cols)}")
