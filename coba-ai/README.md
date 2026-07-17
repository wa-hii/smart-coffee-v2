# RoastSense - Random Forest Coffee Quality Classifier

Pipeline Python untuk mengklasifikasikan kopi berdasarkan **kualitas / cacat
mutu** (Adulterated Quality / High Quality / Low Quality) menggunakan data
pembacaan sensor e-nose 8 channel, sesuai struktur dataset dari jurnal
*MDPI Sensors 10(1):36*.

Label kelas yang dipakai persis sesuai dataset aslinya:
- `AQ_Coffee` → Adulterated_Quality
- `HQ_Coffee` → High_Quality
- `LQ_Coffee` → Low_Quality

## Struktur folder

```
roastsense_rf/
├── data/
│   ├── AQ_Coffee/          # file .txt per sampel, folder = kelas
│   ├── HQ_Coffee/
│   └── LQ_Coffee/
├── src/
│   ├── __init__.py
│   ├── data_loader.py      # baca & parse file .txt sensor, mapping folder->label kualitas
│   ├── feature_extraction.py  # ekstrak fitur statistik (mean/std/max/min/range/slope)
│   ├── train_model.py      # training Random Forest + GridSearchCV
│   ├── evaluate_model.py   # classification report, confusion matrix, feature importance
│   └── predict.py          # prediksi kualitas untuk 1 file sensor baru
├── models/                 # output: model .pkl tersimpan di sini
├── outputs/                # output: plot & report evaluasi
├── main.py                 # entry point, jalankan seluruh pipeline
├── requirements.txt
└── README.md
```

## Format file data (.txt)

Tiap file `.txt` di dalam `data/<Nama_Folder_Kelas>/` berisi (opsional)
header nama sensor lalu satu atau lebih baris angka pembacaan (8 kolom
sesuai urutan sensor). Kalau ada beberapa baris (time-series pembacaan dari
waktu ke waktu), pipeline otomatis menghitung mean/std/slope-nya.

```
1 SP-12A Flammable Gases
1 SP-31 Organic Solvents
1 TGS-813 Combustible gas
1 TGS-842 Methane, natural gas
1 SP-AQ3 Air Quality Control
1 TGS-823 Combustible Gases
1 ST-31 Organic Solvents
1 TGS-800
33.739782   72.056151   22.320113   22.949768   16.178617   45.594388   49.096439   33.202050
```

Contoh file dummy (format sama, angka contoh) sudah disediakan di masing-
masing folder `data/*_Coffee/` supaya kamu bisa langsung coba jalankan
pipeline-nya. **Ganti dengan data asli kamu** sebelum training sungguhan.

## Cara pakai

```bash
pip install -r requirements.txt

# jalankan full pipeline
python main.py --data_dir data --model_dir models --output_dir outputs

# kalau data masih sedikit, matikan grid search biar lebih cepat & stabil
python main.py --no_grid_search

# prediksi 1 file sensor baru pakai model yang sudah dilatih
python -m src.predict data/HQ_Coffee/sample_001.txt
```

## Output yang dihasilkan

- `models/rf_quality_model.pkl` — model Random Forest terlatih
- `models/scaler.pkl`, `models/label_encoder.pkl`, `models/feature_columns.pkl`
- `outputs/classification_report.txt`
- `outputs/confusion_matrix.png`
- `outputs/feature_importance.png` — sensor mana paling berpengaruh ke kualitas kopi

## Catatan jumlah data

Random Forest + GridSearchCV butuh data yang cukup (idealnya puluhan sampel
per kelas). Kalau datasetmu masih sangat sedikit (seperti contoh dummy di
repo ini), `train_test_split` dengan `stratify` bisa gagal karena tiap kelas
minimal butuh 2 sampel untuk dibagi train/test. Tambah jumlah sampel dulu
sebelum training final.
