import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

base_dir = Path(__file__).resolve().parent.parent
csv_path = base_dir / "data" / "medium_20260811_170159.csv"
out_dir = base_dir / "data" / "plots"
out_dir.mkdir(parents=True, exist_ok=True)

# Baca data
try:
    df = pd.read_csv(csv_path)
except FileNotFoundError:
    raise FileNotFoundError(f"File tidak ditemukan: {csv_path}")

# Ambil data collecting saja
if "phase" in df.columns:
    df = df[df["phase"] == "collecting"].copy()

# Pastikan kolom time/sensor ada
x_col = "sample_idx" if "sample_idx" in df.columns else "timestamp"
selected = [
    "adc_tgs822",
    "adc_mq135",
    "adc_tgs2620",
    "adc_tgs2602",
]
selected = [c for c in selected if c in df.columns]
if not selected:
    raise ValueError("Tidak ada kolom sensor yang cocok untuk plot.")

# Konversi numerik
for c in selected:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df = df.dropna(subset=selected)

# Plot
fig, ax = plt.subplots(figsize=(12, 6))
for c in selected:
    ax.plot(df[x_col], df[c], label=c, linewidth=1.8)

ax.set_title("Grafik Data Medium - Sensor E-Nose")
ax.set_xlabel(x_col)
ax.set_ylabel("Nilai ADC")
ax.grid(True, alpha=0.3)
ax.legend(loc="best")
plt.tight_layout()

out_file = out_dir / "medium_sensor_graph.png"
fig.savefig(out_file, dpi=180)
plt.close(fig)

print(f"Grafik berhasil dibuat: {out_file}")
print(f"Jumlah data: {len(df)} baris")
