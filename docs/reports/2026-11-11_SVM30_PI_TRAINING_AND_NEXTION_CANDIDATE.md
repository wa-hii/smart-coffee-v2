# Smart Coffee E-Nose — SVM RBF 9 Fitur, 30 Siklus, Raspberry Pi 5

**Tanggal:** 11 November 2026, WIB. **Branch:** `wahyu`.
**Status:** TRAINING / OFFLINE INFERENCE / REPLAY PI **PASS**;
USB serial fisik, firmware flashing dan Nextion fisik **NOT RUN**.

## 1. Keputusan: gunakan SVM, bukan Random Forest

Menindaklanjuti instruksi pengguna, model kandidat aktif untuk penelitian
diganti menjadi **SVM RBF dengan 9 fitur** dari sensor TGS822, TGS2602,
TGS816. Model RF500 dari pengujian sebelumnya **tidak dihapus**;
artefaknya tetap di staging terpisah, tetapi **tidak digunakan**
dalam alur SVM ini.

Kedua mode firmware source tetap 30 siklus × (purging 25 detik +
collecting 5 detik), nominal **900 pembacaan/15 menit**.

## 2. Fitur dan preprocessing yang benar

Untuk tiap sensor dan siklus:

1. Baseline lokal = median **lima ADC terakhir purging** (sampel 21–25).
2. Respons siklus = mean lima ADC collecting − baseline lokal.
3. Tiga fitur dari 30 respons siklus: `median_phase_response`,
   `mean_phase_response`, `response_early_late` =
   median respons lima siklus terakhir − median lima siklus awal.

Fitur disusun **per sensor**, masing-masing tiga fitur, urutan:
`adc_tgs822`, `adc_tgs2602`, `adc_tgs816`. **Z-score fit hanya
di data training** melalui `Pipeline(StandardScaler(), SVC())`;
Pi tidak boleh melakukan `fit` ulang pada data AI Test.

SVM: kernel RBF, `C=1`, `gamma=scale`,
`class_weight=balanced`, `probability=False`. Tidak ada
model origin atau probabilitas terkalibrasi; `tOrigin`,
`tRConf`, `tOConf` tetap `N/A` jika klasifikasi SVM
nantinya diuji pada layar.

## 3. Training dan bukti data

Sumber: `data/dataset sorting/{a,b,c}/kept/`.
Hanya CSV yang telah **lolos audit struktur**, 30 siklus,
900 sampel, serta deduplikasi `origin-roast-batch`.
**Empat file incomplete di folder kept dikecualikan**:
`L-MING_B75_8d9adafb31744b538fa663e1fef1b18c_INCOMPLETE.csv`,
`L-TOR_B75_ad0a30d7ece544609ad4efcb742504e2_INCOMPLETE.csv`,
`M-GAW_B75_bc7301af72124e398d4edb8626b1836e_INCOMPLETE.csv`,
`M-TEM_B73_a00116bc923c42b888da60e07fad130c_INCOMPLETE.csv`.
Satu duplikat `M-TEM_B62_20261019_175906.csv` tidak dihitung
sebagai sesi independen.

Sembilan fitur **dihitung ulang langsung dari 199 file** dan
dicocokkan terhadap `sensor_signal_metrics.csv` lama,
error absolut kurang dari `1e-7`. SHA256 setiap sumber
dicocokkan terhadap manifest audit; raw data **tidak diubah**.

Training cohort a+b **133 sesi**, LeaveOneGroupOut CV berdasarkan
enam origin, scaler di-*fit* di masing-masing fold training.
Holdout cohort c **66 sesi**, tidak digunakan untuk fit/tuning.

| Metrik | CV enam origin training | Holdout c diagnostik |
|---|---:|---:|
| Balanced accuracy | **0,546883** | **0,652661** |
| Macro-F1 | 0,544430 | **0,601044** |
| Accuracy | 0,548872 | 0,606061 |
| Recall Light | 0,7556 | 0,9286 |
| Recall Medium | 0,4565 | 0,5294 |
| Recall Dark | 0,4286 | 0,5000 |

Confusion matrix testing (urutan Light/Medium/Dark):
`[[13,1,0],[12,18,4],[5,4,9]]`.

Skor mereproduksi benchmark SVM sembilan fitur terdahulu.
Ini **bukan** akurasi blind/prospektif: manual sorting, confounding
perangkat/roast/origin dan independensi spesimen yang belum dibuktikan
tetap membatasi generalisasi.

## 4. Deployment kandidat di Raspberry Pi

Host SSH sebelumnya telah diverifikasi:
`enose-v3@enose-pi5`, Pi 5 Model B Rev 1.1,
Python 3.13.5. Model SVM **dilatih langsung di Pi** menggunakan
venv isolated scikit-learn **1.7.2**, bukan model serialized Windows
yang berasal dari versi berbeda.

Lokasi di Pi:

```text
/home/enose-v3/smart-coffee-stage7/svm30_staging/
    svm30_roast_model.py
    fit_svm30_candidate.py
    svm30_pi_return_bridge.py
    rf30_pi_result_bridge.py
    svm30_model/
        svm30_9feat_candidate.joblib
        svm30_9feat_metadata.json
        holdout_predictions.csv
```

SHA256 **SVM9 candidate joblib**:
```text
4f1f4e75165845867f54905ef3596ac666f3e30b4f65252f881c00b9931531c0
```

File `joblib` hasil training, dataset sorting milik pengguna,
dan matriks fitur per CSV **tidak dipublikasikan ke GitHub**.
Metadata model dan skrip train/inferensi disediakan pada repo.
Model secara eksplisit `deployed_to_production=false`.

## 5. Integrasi ke firmware dan Nextion

Firmware source sebelumnya sudah mempunyai transport balik untuk
AI 30 siklus: `#rf30:<TOKEN>:<light|medium|dark>;`,
`AI_AWAITING_RESULT`, `AI_RESULT_ACK`, token korelasi sesi,
timeout 30 detik, serta update `pResult.tRoast` tanpa perubahan visual.
**Istilah `rf30` adalah nama kontrak transport yang dipertahankan
agar kompatibel, bukan jenis algoritma AI.** SVM memakai string
yang sama, tetapi menjalankan pipeline SVM, bukan RF500.

`svm30_pi_return_bridge.py` mengolah hanya sesi AI Test
30-siklus/900-sampel, menolak label ground truth dari metadata,
menggunakan fitur 9 baseline-corrected dan `StandardScaler`
dalam pipeline. Perintah serial BENCH memiliki dua opt-in eksplisit
dan flag pengawasan onsite + konfirmasi idle. **Mode live TIDAK
dijalankan.** Pada firmware normal `ENABLE_PI_RF30_RETURN=0`,
sehingga hasil tetap `N/A` walaupun data lengkap.

Uji di Pi dengan 900-sampel CSV testing `D-CAT_B80.csv`:

- Preprocessing SVM di Pi: PASS.
- Keluaran kelas `dark`: PASS (label contoh diketahui; bukan blind).
- Perintah kandidat: `#rf30:B1F503A9:dark;`: PASS.
- ACK: **SIMULASI SAJA**.
- USB serial dibuka: **TIDAK**, TX ke MCU **0 bytes**,
  layar Nextion fisik: **belum diuji**.

## 6. Kondisi hardware dan keputusan QA

USB FT232R terakhir terdeteksi sebagai `/dev/ttyUSB0`, seri
`A10KNJBL`, bukan `A10KMM3S` pada pengujian terdahulu.
Kernel 11 November mencatat disconnect/reconnect. Terkini port
tidak memiliki pemilik (`fuser` kosong), `throttled=0x0`,
tetapi perangkat fisik **belum dibuktikan idle/terawasi onsite**.
G0 identitas PCB/backfeed dan izin G2 belum ditutup.

**G2 read-only serial, flashing, 30 siklus dengan aktuator,
serta pengiriman hasil ke Nextion tidak dijalankan pada milestone ini.**
Pemeriksaan SSH/sysfs dan replay file tidak setara dengan validasi
firmware aktual.

## 7. QA yang dijalankan

- `scripts/export_svm30_candidate_features.py`: PASS (199 CSV,
  9 fitur cocok dengan audit lama, 133/66 split).
- `scripts/fit_svm30_candidate.py` di Pi: PASS; checksum output cocok.
- `scripts/svm30_roast_model.py` di Pi: PASS untuk satu CSV real.
- `scripts/svm30_pi_return_bridge.py` di Pi: PASS offline terhadap
  CSV cohort c, menghasilkan paket balik SVM.
- `scripts/test_svm30_candidate.py`: PASS; fail-closed data
  5 siklus, index/fase salah, NaN, timestamp ganda, ADC tidak integral
  pada replay, label tidak boleh dipakai, live gate OFF.
- `scripts/test_rf30_pi_result_bridge.py`: PASS sesudah
  perluasan *predictor adapter*; tidak merusak jalur RF lama.
- `scripts/test_rf30_firmware_result_contract.py`: PASS.
- Perangkat fisik tidak disentuh; **model dipersiapkan,
  bukan dipromosikan untuk produksi**.

## 8. Tindakan fisik berikutnya — setelah persetujuan SOP

1. Operator onsite memastikan FT232 `A10KNJBL` benar PCB
   Smart Coffee yang dimaksud, status **IDLE**, suplai listrik/
   USB backfeed telah diperiksa dan ada pengawas.
2. Setelah izin G2 khusus, buka serial read-only singkat,
   cek `FW_HELLO` / `ACQ_START` untuk versi aktual.
   Jika berbeda, **jangan** kirim perintah model ke firmware lama.
3. Lakukan backup + flashing firmware bench yang enable return
   hanya dengan izin hardware terpisah, kemudian verifikasi perintah
   `#rf30:` dan balasan MCU tanpa aktor terlebih dahulu.
4. Pada G3 terawasi, operator menekan START AI TEST 30 siklus
   sekali; validasi 900 sensor rows, 25+5 tiap siklus, progress,
   stop aman, inferensi SVM, ACK dan halaman `pResult`.
5. Selanjutnya blind test dengan kopi fisik baru lintas
   roast/origin/device dan unknown/air, serta kalibrasi confidence.
