import os
import json
import pandas as pd
import glob

# Konfigurasi path
DATA_DIR = '../data/'
OUTPUT_CSV = '../data/dataset_fitur.csv'

def extract_features():
    all_features = []
    
    # Cari semua file .txt (yang isinya JSON) di folder data
    file_list = glob.glob(os.path.join(DATA_DIR, '*.txt'))
    
    if not file_list:
        print(f"Tidak ada file .txt ditemukan di folder {DATA_DIR}")
        return
        
    for filepath in file_list:
        print(f"Memproses {filepath}...")
        
        # Dictionary untuk menyimpan data ADC sementara per status roasting
        # Struktur: {'light': {'adc_mq135': [], ...}, 'medium': {...}, 'dark': {...}}
        status_data = {}
        
        with open(filepath, 'r') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    status = data.get('status', '').lower()
                    
                    # Kita hanya peduli mengekstrak fitur pada fase light, medium, dark
                    if status in ['light', 'medium', 'dark']:
                        if status not in status_data:
                            status_data[status] = {
                                'adc_mq135': [], 'adc_mq136': [], 'adc_mq137': [], 'adc_mq138': [],
                                'adc_mq2': [], 'adc_mq3': [], 'adc_tgs822': [], 'adc_tgs2620': []
                            }
                        
                        # Masukkan nilai ADC ke dalam list
                        for key in status_data[status].keys():
                            if key in data and data[key] is not None:
                                status_data[status][key].append(data[key])
                                
                except json.JSONDecodeError:
                    continue # Abaikan baris yang bukan JSON valid
                    
        # Ekstrak nilai puncak (Maksimum) dari setiap status/fase di file ini
        for status, sensors in status_data.items():
            feature_row = {}
            feature_row['file_sumber'] = os.path.basename(filepath)
            feature_row['label'] = status
            
            # Cari nilai maximum untuk setiap sensor array
            for sensor_name, values in sensors.items():
                if len(values) > 0:
                    feature_row[f'{sensor_name}_max'] = max(values)
                else:
                    feature_row[f'{sensor_name}_max'] = 0 # Default jika kosong
            
            all_features.append(feature_row)
            
    if all_features:
        # Ubah jadi format tabel dan simpan ke CSV
        df = pd.DataFrame(all_features)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n Ekstraksi selesai! Total {len(df)} sampel data diekstrak.")
        print(f" Data disimpan ke {OUTPUT_CSV}")
        print("\nPreview Data:")
        print(df.head())
    else:
        print("\n Tidak ada data berlabel 'light', 'medium', atau 'dark' yang ditemukan di dalam file-file tersebut.")

if __name__ == "__main__":
    extract_features()
