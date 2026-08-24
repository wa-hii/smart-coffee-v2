import pandas as pd
import matplotlib.pyplot as plt
import os

# Read light data
data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'light_20260810_160508.csv')
if not os.path.exists(data_path):
    import glob
    candidates = glob.glob(os.path.join(os.path.dirname(__file__), '..', 'data', 'light_*.csv'))
    if candidates:
        data_path = candidates[0]
df = pd.read_csv(data_path)

# Sensor columns
sensor_cols = ['adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620', 
               'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816']

# Create figure with subplots
fig, axes = plt.subplots(2, 5, figsize=(18, 10))
fig.suptitle('Light Roast - Sensor Readings Over Time', fontsize=16, fontweight='bold')

axes = axes.flatten()

# Plot each sensor
for idx, sensor in enumerate(sensor_cols):
    axes[idx].plot(df['sample_idx'], df[sensor], marker='o', linewidth=2, markersize=4, color='steelblue')
    axes[idx].set_title(sensor, fontsize=10, fontweight='bold')
    axes[idx].set_xlabel('Sample Index')
    axes[idx].set_ylabel('ADC Value')
    axes[idx].grid(True, alpha=0.3)

plt.tight_layout()

# Buat direktori plots jika belum ada
plots_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'plots')
os.makedirs(plots_dir, exist_ok=True)

output_path = os.path.join(plots_dir, 'light_sensors.png')
plt.savefig(output_path, dpi=100, bbox_inches='tight')
print(f"✓ Grafik disimpan ke: {output_path}")
print(f"✓ Total samples: {len(df)}")
print(f"✓ Data shape: {df.shape}")
print(f"\nStatistik sensor:")
print(df[sensor_cols].describe())

# Display the plot
try:
    plt.show()
except:
    print("GUI tidak tersedia, grafik sudah disimpan.")
