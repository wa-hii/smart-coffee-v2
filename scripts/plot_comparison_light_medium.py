import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import os

# Read data
light_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'light_20260810_160508.csv')
medium_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'medium_20260811_170159.csv')

try:
    light_df = pd.read_csv(light_path)
    medium_df = pd.read_csv(medium_path)
except Exception as e:
    print(f"Error reading files: {e}")
    exit(1)

# Sensor columns
sensor_cols = ['adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620', 
               'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816']

# Calculate average for each sensor
light_avg = light_df[sensor_cols].mean()
medium_avg = medium_df[sensor_cols].mean()

# Create figure with multiple subplots
fig = plt.figure(figsize=(16, 12))

# 1. Bar chart perbandingan rata-rata
ax1 = plt.subplot(2, 2, 1)
x = np.arange(len(sensor_cols))
width = 0.35
bars1 = ax1.bar(x - width/2, light_avg.values, width, label='Light Roast', color='#FF9999', alpha=0.8)
bars2 = ax1.bar(x + width/2, medium_avg.values, width, label='Medium Roast', color='#6666FF', alpha=0.8)
ax1.set_xlabel('Sensors', fontweight='bold')
ax1.set_ylabel('ADC Value (Average)', fontweight='bold')
ax1.set_title('Perbandingan Rata-rata ADC Value', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels(sensor_cols, rotation=45, ha='right')
ax1.legend()
ax1.grid(True, alpha=0.3, axis='y')

# Add value labels on bars
for bars in [bars1, bars2]:
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=8)

# 2. Line plot perbandingan time series (sampling pertama 100 data points)
ax2 = plt.subplot(2, 2, 2)
n_samples = min(100, len(light_df), len(medium_df))
ax2.plot(range(n_samples), light_df['adc_tgs822'][:n_samples], marker='o', label='Light (TGS822)', linewidth=2, markersize=4)
ax2.plot(range(n_samples), medium_df['adc_tgs822'][:n_samples], marker='s', label='Medium (TGS822)', linewidth=2, markersize=4)
ax2.set_xlabel('Sample Index', fontweight='bold')
ax2.set_ylabel('ADC Value', fontweight='bold')
ax2.set_title('Time Series - Sensor TGS822 (100 samples pertama)', fontsize=12, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3)

# 3. Box plot untuk distribusi
ax3 = plt.subplot(2, 2, 3)
data_to_plot = [light_df[sensor_cols].values.flatten(), medium_df[sensor_cols].values.flatten()]
bp = ax3.boxplot(data_to_plot, labels=['Light Roast', 'Medium Roast'], patch_artist=True)
colors = ['#FF9999', '#6666FF']
for patch, color in zip(bp['boxes'], colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.7)
ax3.set_ylabel('ADC Value', fontweight='bold')
ax3.set_title('Distribusi ADC Value', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# 4. Heatmap style comparison untuk setiap sensor
ax4 = plt.subplot(2, 2, 4)
comparison_data = np.array([light_avg.values, medium_avg.values])
im = ax4.imshow(comparison_data, cmap='YlOrRd', aspect='auto')
ax4.set_yticks([0, 1])
ax4.set_yticklabels(['Light Roast', 'Medium Roast'])
ax4.set_xticks(range(len(sensor_cols)))
ax4.set_xticklabels(sensor_cols, rotation=45, ha='right')
ax4.set_title('Heatmap Perbandingan Sensor', fontsize=12, fontweight='bold')

# Add values in heatmap
for i in range(2):
    for j in range(len(sensor_cols)):
        text = ax4.text(j, i, f'{int(comparison_data[i, j])}',
                       ha="center", va="center", color="black", fontsize=9, fontweight='bold')

plt.colorbar(im, ax=ax4)

plt.suptitle('Perbandingan Sensor Reading: Light vs Medium Roast', fontsize=16, fontweight='bold', y=0.995)
plt.tight_layout()

# Buat direktori plots jika belum ada
plots_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'plots')
os.makedirs(plots_dir, exist_ok=True)

output_path = os.path.join(plots_dir, 'light_vs_medium_comparison.png')
plt.savefig(output_path, dpi=100, bbox_inches='tight')
print(f"✓ Grafik disimpan ke: {output_path}\n")

# Print statistics
print("=" * 70)
print("STATISTIK LIGHT ROAST:")
print("=" * 70)
print(light_df[sensor_cols].describe().round(2))

print("\n" + "=" * 70)
print("STATISTIK MEDIUM ROAST:")
print("=" * 70)
print(medium_df[sensor_cols].describe().round(2))

print("\n" + "=" * 70)
print("PERBANDINGAN RATA-RATA:")
print("=" * 70)
comparison_df = pd.DataFrame({
    'Light Roast': light_avg,
    'Medium Roast': medium_avg,
    'Selisih': medium_avg - light_avg,
    'Persentase Peningkatan (%)': ((medium_avg - light_avg) / light_avg * 100).round(2)
})
print(comparison_df.round(2))

try:
    plt.show()
except:
    print("\nGUI tidak tersedia, grafik sudah disimpan.")
