import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Use absolute paths
base_dir = Path(r"f:\MBKM ADB ENOSE\smart-coffee-v2")
light_path = base_dir / "data" / "light_20260810_160508.csv"
medium_path = base_dir / "data" / "medium_20260811_170159.csv"
out_dir = base_dir / "data" / "plots"
out_dir.mkdir(parents=True, exist_ok=True)

# Baca data
print("Membaca data light...")
light_df = pd.read_csv(light_path)
print(f"Light data shape: {light_df.shape}")

print("Membaca data medium...")
medium_df = pd.read_csv(medium_path)
print(f"Medium data shape: {medium_df.shape}")

# Filter data collecting
light_df = light_df[light_df["phase"] == "collecting"].copy()
medium_df = medium_df[medium_df["phase"] == "collecting"].copy()

# Sensor columns
sensor_cols = ['adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620', 
               'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816']

# Konversi numeric
for col in sensor_cols:
    if col in light_df.columns:
        light_df[col] = pd.to_numeric(light_df[col], errors='coerce')
    if col in medium_df.columns:
        medium_df[col] = pd.to_numeric(medium_df[col], errors='coerce')

# Calculate average
light_avg = light_df[sensor_cols].mean()
medium_avg = medium_df[sensor_cols].mean()

print("\nMembuat grafik...")

# Create figure with 2x2 subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Perbandingan Light Roast vs Medium Roast', fontsize=16, fontweight='bold')

# 1. Bar chart perbandingan rata-rata
ax = axes[0, 0]
x = np.arange(len(sensor_cols))
width = 0.35
ax.bar(x - width/2, light_avg.values, width, label='Light Roast', color='#FF9999', alpha=0.8)
ax.bar(x + width/2, medium_avg.values, width, label='Medium Roast', color='#6666FF', alpha=0.8)
ax.set_xlabel('Sensors', fontweight='bold')
ax.set_ylabel('ADC Value (Average)', fontweight='bold')
ax.set_title('Perbandingan Rata-rata ADC Value')
ax.set_xticks(x)
ax.set_xticklabels(sensor_cols, rotation=45, ha='right', fontsize=8)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

# 2. Box plot
ax = axes[0, 1]
box_data = [light_df[sensor_cols].values.flatten(), medium_df[sensor_cols].values.flatten()]
bp = ax.boxplot(box_data, labels=['Light Roast', 'Medium Roast'], patch_artist=True)
for patch, color in zip(bp['boxes'], ['#FF9999', '#6666FF']):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
ax.set_ylabel('ADC Value', fontweight='bold')
ax.set_title('Distribusi ADC Value')
ax.grid(True, alpha=0.3, axis='y')

# 3. Time series comparison (TGS822 sensor)
ax = axes[1, 0]
n_samples = min(200, len(light_df), len(medium_df))
ax.plot(range(n_samples), light_df['adc_tgs822'].iloc[:n_samples].values, 
        label='Light', linewidth=2, color='#FF9999')
ax.plot(range(n_samples), medium_df['adc_tgs822'].iloc[:n_samples].values, 
        label='Medium', linewidth=2, color='#6666FF')
ax.set_xlabel('Sample Index', fontweight='bold')
ax.set_ylabel('ADC Value', fontweight='bold')
ax.set_title('Time Series - Sensor TGS822 (200 samples)')
ax.legend()
ax.grid(True, alpha=0.3)

# 4. Percentage difference
ax = axes[1, 1]
pct_diff = ((medium_avg - light_avg) / light_avg * 100)
colors = ['#FF6666' if x < 0 else '#66FF66' for x in pct_diff.values]
bars = ax.barh(sensor_cols, pct_diff.values, color=colors, alpha=0.8)
ax.set_xlabel('Persentase Perubahan (%)', fontweight='bold')
ax.set_title('Medium vs Light (% perubahan)')
ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
ax.grid(True, alpha=0.3, axis='x')

# Add value labels
for i, bar in enumerate(bars):
    width = bar.get_width()
    ax.text(width, bar.get_y() + bar.get_height()/2., f'{width:.1f}%',
            ha='left' if width > 0 else 'right', va='center', fontsize=9)

plt.tight_layout()

# Save figure
output_path = out_dir / "light_vs_medium_comparison.png"
print(f"Menyimpan grafik ke: {output_path}")
plt.savefig(str(output_path), dpi=100, bbox_inches='tight')
print(f"✓ Grafik berhasil disimpan!")

# Print statistics
print("\n" + "="*70)
print("STATISTIK LIGHT ROAST:")
print("="*70)
print(light_df[sensor_cols].describe().round(2))

print("\n" + "="*70)
print("STATISTIK MEDIUM ROAST:")
print("="*70)
print(medium_df[sensor_cols].describe().round(2))

print("\n" + "="*70)
print("PERBANDINGAN RATA-RATA:")
print("="*70)
comparison_df = pd.DataFrame({
    'Light': light_avg.round(2),
    'Medium': medium_avg.round(2),
    'Selisih': (medium_avg - light_avg).round(2),
    'Pct Change (%)': ((medium_avg - light_avg) / light_avg * 100).round(2)
})
print(comparison_df)

print(f"\n✓ Selesai! Grafik tersimpan di: {output_path}")
