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
dark_path = base_dir / "data" / "dark_20260813_132219.csv"
out_dir = base_dir / "data" / "plots"
out_dir.mkdir(parents=True, exist_ok=True)

# Baca data
print("Membaca data light...")
light_df = pd.read_csv(light_path)
print(f"Light data shape: {light_df.shape}")

print("Membaca data medium...")
medium_df = pd.read_csv(medium_path)
print(f"Medium data shape: {medium_df.shape}")

print("Membaca data dark (Jawa Barat)...")
dark_df = pd.read_csv(dark_path)
print(f"Dark data shape: {dark_df.shape}")

# Filter data collecting
light_df = light_df[light_df["phase"] == "collecting"].copy()
medium_df = medium_df[medium_df["phase"] == "collecting"].copy()
dark_df = dark_df[dark_df["phase"] == "collecting"].copy()

# Sensor columns
sensor_cols = ['adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620', 
               'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816']

# Konversi numeric
for col in sensor_cols:
    if col in light_df.columns:
        light_df[col] = pd.to_numeric(light_df[col], errors='coerce')
    if col in medium_df.columns:
        medium_df[col] = pd.to_numeric(medium_df[col], errors='coerce')
    if col in dark_df.columns:
        dark_df[col] = pd.to_numeric(dark_df[col], errors='coerce')

# Calculate average
light_avg = light_df[sensor_cols].mean()
medium_avg = medium_df[sensor_cols].mean()
dark_avg = dark_df[sensor_cols].mean()

print("\nMembuat grafik 3 jenis kopi...")

# Create figure with 2x2 subplots
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
fig.suptitle('Perbandingan Sensor Reading: Light vs Medium vs Jawa Barat (Dark)', 
             fontsize=16, fontweight='bold')

# 1. Bar chart perbandingan rata-rata
ax = axes[0, 0]
x = np.arange(len(sensor_cols))
width = 0.25
colors = ['#FF9999', '#6666FF', '#8B4513']  # Red, Blue, Brown for Dark
bars1 = ax.bar(x - width, light_avg.values, width, label='Light Roast', color=colors[0], alpha=0.8)
bars2 = ax.bar(x, medium_avg.values, width, label='Medium Roast', color=colors[1], alpha=0.8)
bars3 = ax.bar(x + width, dark_avg.values, width, label='Jawa Barat (Dark)', color=colors[2], alpha=0.8)

ax.set_xlabel('Sensors', fontweight='bold')
ax.set_ylabel('ADC Value (Average)', fontweight='bold')
ax.set_title('Perbandingan Rata-rata ADC Value')
ax.set_xticks(x)
ax.set_xticklabels(sensor_cols, rotation=45, ha='right', fontsize=8)
ax.legend()
ax.grid(True, alpha=0.3, axis='y')

# 2. Box plot untuk distribusi
ax = axes[0, 1]
box_data = [light_df[sensor_cols].values.flatten(), 
            medium_df[sensor_cols].values.flatten(),
            dark_df[sensor_cols].values.flatten()]
bp = ax.boxplot(box_data, labels=['Light', 'Medium', 'Jawa Barat'], patch_artist=True)
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
ax.set_ylabel('ADC Value', fontweight='bold')
ax.set_title('Distribusi ADC Value')
ax.grid(True, alpha=0.3, axis='y')

# 3. Time series comparison (TGS822 sensor)
ax = axes[1, 0]
n_samples = min(200, len(light_df), len(medium_df), len(dark_df))
ax.plot(range(n_samples), light_df['adc_tgs822'].iloc[:n_samples].values, 
        label='Light', linewidth=2, color=colors[0])
ax.plot(range(n_samples), medium_df['adc_tgs822'].iloc[:n_samples].values, 
        label='Medium', linewidth=2, color=colors[1])
ax.plot(range(n_samples), dark_df['adc_tgs2602'].iloc[:n_samples].values, 
        label='Jawa Barat (Dark)', linewidth=2, color=colors[2])
ax.set_xlabel('Sample Index', fontweight='bold')
ax.set_ylabel('ADC Value', fontweight='bold')
ax.set_title('Time Series - Sensor Comparison (200 samples)')
ax.legend()
ax.grid(True, alpha=0.3)

# 4. Heatmap style comparison
ax = axes[1, 1]
comparison_data = np.array([light_avg.values, medium_avg.values, dark_avg.values])
im = ax.imshow(comparison_data, cmap='YlOrRd', aspect='auto')
ax.set_yticks([0, 1, 2])
ax.set_yticklabels(['Light', 'Medium', 'Jawa Barat (Dark)'])
ax.set_xticks(range(len(sensor_cols)))
ax.set_xticklabels(sensor_cols, rotation=45, ha='right', fontsize=9)
ax.set_title('Heatmap Perbandingan Sensor')

# Add values in heatmap
for i in range(3):
    for j in range(len(sensor_cols)):
        text = ax.text(j, i, f'{int(comparison_data[i, j])}',
                       ha="center", va="center", color="black", fontsize=8, fontweight='bold')

plt.colorbar(im, ax=ax, label='ADC Value')

plt.tight_layout()

# Save figure
output_path = out_dir / "light_medium_jawa_barat_comparison.png"
print(f"\nMenyimpan grafik ke: {output_path}")
plt.savefig(str(output_path), dpi=100, bbox_inches='tight')
print(f"✓ Grafik berhasil disimpan!\n")

# Print statistics
print("=" * 80)
print("STATISTIK LIGHT ROAST:")
print("=" * 80)
print(light_df[sensor_cols].describe().round(2))

print("\n" + "=" * 80)
print("STATISTIK MEDIUM ROAST:")
print("=" * 80)
print(medium_df[sensor_cols].describe().round(2))

print("\n" + "=" * 80)
print("STATISTIK JAWA BARAT (DARK ROAST):")
print("=" * 80)
print(dark_df[sensor_cols].describe().round(2))

print("\n" + "=" * 80)
print("PERBANDINGAN RATA-RATA SENSOR:")
print("=" * 80)
comparison_df = pd.DataFrame({
    'Light': light_avg.round(2),
    'Medium': medium_avg.round(2),
    'Jawa Barat': dark_avg.round(2),
    'Light→Medium (%)': ((medium_avg - light_avg) / light_avg * 100).round(2),
    'Medium→Jawa Barat (%)': ((dark_avg - medium_avg) / medium_avg * 100).round(2),
    'Light→Jawa Barat (%)': ((dark_avg - light_avg) / light_avg * 100).round(2),
})
print(comparison_df)

print("\n" + "=" * 80)
print(f"✓ Selesai! Grafik tersimpan di: {output_path}")
print("=" * 80)
