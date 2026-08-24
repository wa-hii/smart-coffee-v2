import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
import sys

print("Script started", file=sys.stderr)

try:
    # Read data
    light_path = r"f:\MBKM ADB ENOSE\smart-coffee-v2\data\light_20260810_160508.csv"
    medium_path = r"f:\MBKM ADB ENOSE\smart-coffee-v2\data\medium_20260811_170159.csv"
    
    print(f"Reading light data from: {light_path}", file=sys.stderr)
    light_df = pd.read_csv(light_path)
    print(f"Light data shape: {light_df.shape}", file=sys.stderr)
    
    print(f"Reading medium data from: {medium_path}", file=sys.stderr)
    medium_df = pd.read_csv(medium_path)
    print(f"Medium data shape: {medium_df.shape}", file=sys.stderr)
    
    # Sensor columns
    sensor_cols = ['adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611', 'adc_tgs2620', 
                   'adc_tgs2600', 'adc_tgs2602', 'adc_mq8', 'adc_tgs813', 'adc_tgs816']
    
    # Calculate average
    light_avg = light_df[sensor_cols].mean()
    medium_avg = medium_df[sensor_cols].mean()
    
    print("Creating figure...", file=sys.stderr)
    
    # Create simple comparison chart
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Light vs Medium Roast Comparison', fontsize=14, fontweight='bold')
    
    # 1. Bar chart
    ax = axes[0, 0]
    x = np.arange(len(sensor_cols))
    width = 0.35
    ax.bar(x - width/2, light_avg.values, width, label='Light', alpha=0.8)
    ax.bar(x + width/2, medium_avg.values, width, label='Medium', alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(sensor_cols, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('ADC Value')
    ax.set_title('Average ADC Values')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. Box plot
    ax = axes[0, 1]
    ax.boxplot([light_df[sensor_cols].values.flatten(), medium_df[sensor_cols].values.flatten()],
               labels=['Light', 'Medium'])
    ax.set_ylabel('ADC Value')
    ax.set_title('Distribution')
    ax.grid(True, alpha=0.3)
    
    # 3. Line comparison
    ax = axes[1, 0]
    n = min(100, len(light_df), len(medium_df))
    ax.plot(light_df['adc_tgs822'][:n].values, label='Light TGS822', linewidth=2)
    ax.plot(medium_df['adc_tgs822'][:n].values, label='Medium TGS822', linewidth=2)
    ax.set_xlabel('Sample Index')
    ax.set_ylabel('ADC Value')
    ax.set_title('TGS822 Sensor (100 samples)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. Statistics table
    ax = axes[1, 1]
    ax.axis('off')
    
    stats_text = "STATISTICS\n\nLight Roast:\n"
    for sensor in sensor_cols[:5]:
        stats_text += f"  {sensor}: {light_avg[sensor]:.0f}\n"
    
    stats_text += "\nMedium Roast:\n"
    for sensor in sensor_cols[:5]:
        stats_text += f"  {sensor}: {medium_avg[sensor]:.0f}\n"
    
    ax.text(0.1, 0.5, stats_text, fontfamily='monospace', fontsize=9, verticalalignment='center')
    
    plt.tight_layout()
    
    # Save figure
    output_path = r"f:\MBKM ADB ENOSE\smart-coffee-v2\data\plots\light_vs_medium_comparison.png"
    print(f"Saving to: {output_path}", file=sys.stderr)
    plt.savefig(output_path, dpi=100, bbox_inches='tight')
    print(f"SUCCESS: Grafik disimpan ke {output_path}", file=sys.stderr)
    
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
