import os
import glob
import pandas as pd
import numpy as np

# Configuration paths
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPTS_DIR, '..', 'data')
ANOMALY_DIR = os.path.join(DATA_DIR, 'anomalies')
os.makedirs(ANOMALY_DIR, exist_ok=True)

ADC_COLS = [
    'adc_tgs822', 'adc_mq135', 'adc_mq9', 'adc_tgs2611',
    'adc_tgs2620', 'adc_tgs2600', 'adc_tgs2602', 'adc_mq8',
    'adc_tgs813', 'adc_tgs816'
]

def load_one_clean_file():
    """Load a clean CSV file from data folder to use as template."""
    csv_files = glob.glob(os.path.join(DATA_DIR, '*.csv'))
    csv_files = [f for f in csv_files if 'dataset_fitur' not in os.path.basename(f) and 'anomalies' not in f]
    if not csv_files:
        raise FileNotFoundError("Tidak ada file CSV bersih untuk dijadikan template.")
    return csv_files[0]

def create_dead_sensor_anomaly(clean_filepath):
    """Simulates a sensor failing and producing flat values (e.g. 0 or static value)."""
    df = pd.read_csv(clean_filepath)
    filename = os.path.basename(clean_filepath)
    
    # We simulate adc_mq135 sensor going dead (getting stuck at 0)
    failed_sensor = 'adc_mq135'
    df[failed_sensor] = 0 # stuck at 0
    
    output_path = os.path.join(ANOMALY_DIR, f'dead_sensor_{filename}')
    df.to_csv(output_path, index=False)
    print(f"[OK] Membuat anomali 'Dead Sensor' di: {output_path}")

def create_spike_noise_anomaly(clean_filepath):
    """Simulates random spikes/high frequency noise due to electrical interference."""
    df = pd.read_csv(clean_filepath)
    filename = os.path.basename(clean_filepath)
    
    # We add random huge spikes (+5000) to 5% of the data points for adc_tgs822
    target_sensor = 'adc_tgs822'
    n_spikes = int(len(df) * 0.05)
    random_indices = np.random.choice(df.index, size=n_spikes, replace=False)
    
    df.loc[random_indices, target_sensor] = df.loc[random_indices, target_sensor] + 5000
    
    output_path = os.path.join(ANOMALY_DIR, f'spike_noise_{filename}')
    df.to_csv(output_path, index=False)
    print(f"[OK] Membuat anomali 'Spike Noise' di: {output_path}")

def create_incomplete_purging_anomaly(clean_filepath):
    """Simulates starting the test before purging is complete, shifting baseline upwards."""
    df = pd.read_csv(clean_filepath)
    filename = os.path.basename(clean_filepath)
    
    # Shifts all MQ/TGS values upwards by 3000 ADC units (baseline shift)
    for col in ADC_COLS:
        df[col] = df[col] + 3000
        
    output_path = os.path.join(ANOMALY_DIR, f'shifted_baseline_{filename}')
    df.to_csv(output_path, index=False)
    print(f"[OK] Membuat anomali 'Baseline Shift' di: {output_path}")

def create_ambient_alcohol_anomaly(clean_filepath):
    """Simulates alcohol vapor/hand sanitizer contamination in the room, saturating all sensors."""
    df = pd.read_csv(clean_filepath)
    filename = os.path.basename(clean_filepath)
    
    # Contamination during the collecting phase:
    # All sensors shoot up to near maximum ADC limit (e.g. 15000+)
    collecting_mask = df['phase'] == 'collecting'
    for col in ADC_COLS:
        df.loc[collecting_mask, col] = np.minimum(df.loc[collecting_mask, col] + 12000, 20000)
        
    output_path = os.path.join(ANOMALY_DIR, f'ambient_contamination_{filename}')
    df.to_csv(output_path, index=False)
    print(f"[OK] Membuat anomali 'Ambient Contamination' di: {output_path}")

if __name__ == '__main__':
    try:
        template_file = load_one_clean_file()
        print(f"Menggunakan template file: {template_file}")
        print("Generating anomalies...")
        create_dead_sensor_anomaly(template_file)
        create_spike_noise_anomaly(template_file)
        create_incomplete_purging_anomaly(template_file)
        create_ambient_alcohol_anomaly(template_file)
        print("\n[SUKSES] Semua file anomali disimpan di folder data/anomalies/")
    except Exception as e:
        print(f"Error: {e}")
