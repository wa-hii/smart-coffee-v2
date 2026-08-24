# Platform Guide — Smart Coffee E-NOSE AI

Dokumentasi setup dan deployment untuk 3 platform utama: **ESP32**, **ATmega2560**, dan **Raspberry Pi**.

---

## 📋 Perbandingan Platform

| Aspek | ESP32 | ATmega2560 | Raspberry Pi |
|-------|-------|-----------|--------------|
| **RAM** | 520 KB | 8 KB | 1-8 GB |
| **Flash** | 4 MB | 256 KB | MicroSD (32 GB+) |
| **Clock** | 240 MHz | 16 MHz | 1.5+ GHz (Quad-core) |
| **Model Size** | ~60 KB | ~30 KB | ~100 KB |
| **Inference Time** | ~10ms | ~50ms | ~1ms |
| **OS** | FreeRTOS | Bare-metal | Linux |
| **Bahasa** | C++ (Arduino) | C++ (Arduino) | Python 3 |
| **Koneksi** | WiFi + BLE | Serial | Ethernet/WiFi |
| **Cost** | $5-10 | $30-40 | $35-55 |

---

## 🚀 ESP32 Setup

### Hardware Requirements
- ESP32 DevKit or similar
- ADS1115 ADC modules (I2C x2)
- MQ/TGS gas sensors
- Nextion display (optional)
- Relay module untuk actuator

### Software Setup

#### 1. Install PlatformIO
```bash
pip install platformio
```

#### 2. Clone repo dan setup dependencies
```bash
cd smart-coffee-v2
pio run --target upload  # Compile dan upload
```

#### 3. Train model dengan hyperparameter untuk ESP32
```bash
python scripts/4_train_rf.py
```
Menghasilkan: `include/model_rf.h` (~ 60 KB)

#### 4. Enable inference di firmware
Edit `src/main.cpp`:
```cpp
#define USE_ON_DEVICE_INFERENCE 1
```

#### 5. Flash ke ESP32
```bash
pio run --target upload
```

#### 6. Test via Serial Monitor
```bash
# Kirim command
#start;

# Setelah 10 siklus collecting, output:
{"event":"INFERENCE","result":"medium","feat_count":180}
```

### Performance
- **Model size**: ~60 KB
- **Inference time**: ~10 ms
- **Memory used**: ~40 KB RAM (dict + model)
- **Accuracy**: Baseline ~85-90%

---

## 🎛️ ATmega2560 Setup

### Hardware Requirements
- Arduino Mega 2560 (bisa clone)
- ADS1115 ADC modules (I2C x2)
- MQ/TGS gas sensors
- Relay module untuk actuator

### Software Setup

#### 1. Install Arduino IDE
```bash
# Windows/Mac/Linux
# Download dari https://www.arduino.cc/en/software
```

#### 2. Setup libraries di Arduino IDE
```
Sketch → Include Library → Manage Libraries
Cari dan install:
  - Wire (built-in)
  - TaskScheduler
  - DFRobot_MLX90614
  - Nextion Interface (jika ada display)
```

#### 3. Generate optimized model untuk ATmega
```bash
# Pastikan sudah train model di Python dulu
python scripts/4_train_rf.py

# Train sekaligus generate model yang dioptimalkan untuk ATmega
python scripts/4_train_rf.py

# Alternatif: generate ulang dari model joblib yang sudah ada
python scripts/generate_model_atmega.py \
  --model data/model_rf.joblib \
  --output include/model_rf_atmega.h \
  --max-trees 8 \
  --max-depth 4
```

Menghasilkan: `include/model_rf_atmega.h` (~ 25-30 KB)

#### 4. Setup source code
Firmware utama repo sudah dikonfigurasi untuk ATmega2560:

```cpp
Edit `platformio.ini` dan ubah `USE_ON_DEVICE_INFERENCE=0` menjadi `1`,
lalu build dan upload dengan PlatformIO.
```

#### 5. Upload ke ATmega
```bash
# Di Arduino IDE
Tools → Board → Arduino Mega or Mega 2560
Tools → Port → [pilih COM port]
Sketch → Upload
```

#### 6. Monitor output
```bash
# Tools → Serial Monitor (115200 baud)
# Kirim: #start;
# Tunggu ~300 detik (180s collecting + 60s purging × 1.5 untuk overhead)
# Output: {"event":"INFERENCE","result":"light","samples":180}
```

### Performance
- **Model size**: ~25-30 KB (pada Flash)
- **Inference time**: ~50-100 ms
- **Memory used**: ~2-3 KB RAM (hanya accumulator)
- **Accuracy**: Sedikit lebih rendah (80-85%) karena tree lebih shallow
- **⚠️ Limitation**: Tidak bisa multitasking, state machine harus sequential

### Tips Optimasi
- Gunakan `--max-trees 6` untuk model super ringan
- Reduce sampling rate jika inference terlalu lambat
- Hindari Serial print di loop utama (use interrupt-driven)
- Disable EEPROM writes jika RAM terlalu tight

---

## 🍓 Raspberry Pi Setup

### Hardware Requirements
- Raspberry Pi 4B (recommended) atau Pi 3B+
- MicroSD card 32 GB Class 10
- Adapter power USB-C (5V 3A)
- USB-UART untuk connect ke sensor array
- Optional: Relay HAT untuk actuator

### Software Setup

#### 1. Install Raspberry Pi OS
```bash
# Download Raspberry Pi Imager
# Write Raspberry Pi OS (Lite) ke microSD
# Boot Raspberry Pi
```

#### 2. Setup Python environment
```bash
# SSH ke Pi
ssh pi@raspberrypi.local

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install -y python3 python3-pip python3-numpy
pip3 install scikit-learn pandas joblib

# Optional: Install untuk data visualization dan monitoring
pip3 install matplotlib seaborn flask mqtt
```

#### 3. Setup inference environment
```bash
# Clone repo (via USB atau network)
cd smart-coffee-v2

# Install ke venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: Tambah di requirements.txt untuk Raspi
pip install paho-mqtt  # Untuk MQTT publish
pip install Flask      # Untuk web dashboard
```

#### 4. Train model di Pi (atau transfer dari host)
```bash
# Opsi A: Train langsung di Pi (lambat, ~2-5 menit)
python scripts/4_train_rf.py

# Opsi B: Transfer model dari host
# (scp model_rf.joblib dari komputer ke Pi)
scp data/model_rf.joblib pi@raspberrypi.local:~/smart-coffee-v2/data/
```

Menghasilkan: `data/model_rf.joblib` (~ 50-100 KB)

#### 5. Setup data acquisition
**Option A: Real-time dari sensor array via Serial**
```bash
# Pastikan USB-UART connected ke GPIO (atau USB serial adapter)
ls /dev/tty*  # Cari device (misal /dev/ttyUSB0)

# Buat script acquire_and_infer.py
python scripts/inference_rpi.py \
  --model data/model_rf.joblib \
  --input /dev/ttyUSB0 \
  --mode realtime
```

**Option B: Batch processing dari CSV**
```bash
python scripts/inference_rpi.py \
  --model data/model_rf.joblib \
  --input data/light_20260813_115343.csv \
  --mode batch
```

#### 6. Setup automated monitoring (optional)
Buat cron job untuk monitor acquisition setiap jam:
```bash
# crontab -e
0 * * * * cd ~/smart-coffee-v2 && python scripts/inference_rpi.py \
  --model data/model_rf.joblib --input data/latest.csv \
  >> logs/inference.log 2>&1
```

#### 7. Web dashboard (optional)
```bash
# Run dashboard server
python scripts/5_realtime_dashboard.py --host 0.0.0.0 --port 5000

# Akses dari browser
# http://raspberrypi.local:5000
```

### Performance
- **Model size**: ~100 KB (pickle/joblib)
- **Inference time**: ~1-5 ms (sangat cepat!)
- **Memory used**: ~50-100 MB (banyak resources)
- **Throughput**: Bisa process ribuan sampel per detik
- **Accuracy**: Sama dengan training (85-90%)

### Integration dengan Cloud/IoT

#### MQTT Publisher
```python
import paho.mqtt.client as mqtt
from inference_rpi import InferenceRPi

inf = InferenceRPi('data/model_rf.joblib')
client = mqtt.Client()
client.connect("mqtt.broker.com", 1883)

# Setelah inference
result = inf.predict()
client.publish("coffee/inference", result.to_json())
```

#### REST API
```python
from flask import Flask, jsonify
app = Flask(__name__)
inf = InferenceRPi('data/model_rf.joblib')

@app.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.json
    inf.reset()
    inf.accumulate(data['adc_values'])
    result = inf.predict()
    return jsonify(result.to_dict())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## 📊 Model Training & Validation

### Universal Training Script
Sama untuk semua platform:
```bash
python scripts/4_train_rf.py
```

Output:
- `data/dataset_fitur.csv` — Features untuk referensi
- `include/model_rf.h` — ESP32 version
- `data/model_rf.joblib` — Python/Raspberry Pi version

### Validasi Accuracy
```bash
python scripts/6_validate_dataset.py
```

Output:
- Confusion matrix
- Classification report (precision, recall, F1)
- Feature importance ranking

---

## 🔄 Workflow Typical Development

### Phase 1: Development (Host Machine)
```bash
# 1. Collect data dengan Arduino/ESP32/etc
python scripts/3_collect_data.py

# 2. Extract features
python scripts/1_ekstraksi_fitur.py

# 3. Train model
python scripts/4_train_rf.py

# 4. Validate
python scripts/6_validate_dataset.py
```

### Phase 2: Deployment

**Untuk ESP32:**
```bash
# Generate model C++ header
python scripts/4_train_rf.py
# ↓ include/model_rf.h generated

# Update main.cpp
# #define USE_ON_DEVICE_INFERENCE 1

# Build & flash
pio run --target upload
```

**Untuk ATmega:**
```bash
# Generate optimized model
python scripts/generate_model_atmega.py

# Update Arduino code dengan inference_atmega.h
# Upload via Arduino IDE
```

**Untuk Raspberry Pi:**
```bash
# Transfer model & script ke Pi
scp scripts/inference_rpi.py pi@raspberrypi:~/
scp data/model_rf.joblib pi@raspberrypi:~/

# Run inference
ssh pi@raspberrypi python inference_rpi.py --model model_rf.joblib
```

---

## 🛠️ Troubleshooting

### ESP32
| Error | Solution |
|-------|----------|
| `model_rf.h: No such file` | Run `python scripts/4_train_rf.py` first |
| `Out of memory` | Reduce `RF_N_ESTIMATORS` in 4_train_rf.py |
| Inference timeout | Reduce sampling cycle time atau increase WiFi buffer |

### ATmega
| Error | Solution |
|-------|----------|
| `Sketch too large` | Reduce model depth/trees; use `--max-trees 6` |
| `Low memory` | Disable debug Serial.print; use PROGMEM for strings |
| Slow inference | Normal (16 MHz clock); consider ESP32 |

### Raspberry Pi
| Error | Solution |
|-------|----------|
| `ModuleNotFoundError: sklearn` | `pip3 install scikit-learn` |
| Serial port permission denied | `sudo usermod -a -G dialout $USER` |
| Slow inference | Model too large; reduce features atau trees |

---

## 📚 References

- [Scikit-learn RandomForest](https://scikit-learn.org/stable/modules/ensemble.html#forest)
- [Arduino Mega 2560 Specs](https://store.arduino.cc/products/arduino-mega-2560-rev3)
- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [TinyML on Microcontrollers](https://www.tensorflow.org/lite/microcontrollers)

---

**Last Updated**: August 2026
**Author**: E-NOSE Coffee Project Team
