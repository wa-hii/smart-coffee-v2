# B1–B3 selesai secara offline — Embedded SVM30 ATmega2560

**Tanggal:** 11 November 2026 (WIB). **Branch:** `wahyu`.

**Status:** B1 golden, B2 streaming feature, B3 native SVM/AVR compile-only **PASS**.
**Belum dilakukan:** flashing, pengujian MCU fisik, restart, USB serial,
aktuator, perubahan Nextion/HMI, atau integrasi firmware utama B4.

## Keputusan model dan batas data

- **Model asli milik tim**: `final_svm.joblib`, hash SHA256
  `d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33`.
- Penjelasan fitur asli: `predict_roast_svm.py`, hash SHA256
  `f21aa7d50bf677d145a55776ff9cd842e0d957563ea657232c8f88a0d6bba133`.
- Bundle benar-benar berisi SVC RBF gamma=0.1, C=1,
  scaler 30 fitur, support vectors `[44,34,47]` (total 125),
  `dual_coef_.shape=(2,125)`, `intercept_.shape=(3,)`,
  kelas `dark/light/medium` (urutan alfabetis).
- Tidak ada retraining, penghapusan fitur, normalisasi baseline
  tambahan, atau penggunaan model 9 fitur yang berbeda.
- Angka nested CV 85,23% dari metadata pengguna **tidak dijadikan
  klaim akurasi firmware**. Parity tests hanya membuktikan kesetaraan
  perhitungan pada rekaman yang diuji.

## B1 — Golden reference (PASS, offline)

- Memakai helper Python asli dari pengguna untuk ekstraksi fitur
  `extract_features_for_names` dan bundle asli untuk
  `scaler.transform` + `SVC.predict`.
- Input disaring ketat sebelum menggunakan helper asli: wajib
  **30 siklus × 25 sampel purging + 5 collecting**, 900 baris,
  timestamp naik, urutan fase/indeks tepat, semua 10 ADC bernilai
  numerik integral dalam rentang 0–32767; file CSV harus cocok hash
  yang dicatat audit dataset. Label/origin/nama file **tidak
  diteruskan ke mesin model**.
- Total **199 CSV** dari tiga cohort yang telah lolos
  validasi struktur, manual-kept dan dedup; mencakup kelas
  dark, light, medium. Golden JSON berisi fitur Python, fitur
  native, vektor scaled, skor pairwise dan prediksi per file.
- Referensi sklearn **1.7.2** (sama dengan versi model
  terserialisasi) dijalankan dalam venv Python 3.10 yang
  **terisolasi di `private/.venv_svm_reference`**.
  Tidak ada `InconsistentVersionWarning` pada validasi akhir.
  Sebagai cross-check, 199 prediksi juga sama pada sklearn 1.9.0.
- Semua **golden vectors per-file disimpan di
  `private/svm30_golden_scores_full199.json`** (gitignored);
  tidak dipublikasikan ke GitHub bersama model/data turunan.

## B2 — 30 fitur streaming C++ (PASS native)

- Modul: `src/embedded_svm30_features.h/.cpp`.
- Empat sensor aktif: TGS822 (ADC0), TGS2602 (ADC6),
  TGS816 (ADC9), MQ8 (ADC7); sepuluh kanal tetap diterima
  dalam urutan `SensorArray` lama.
- Memori **konstan terhadap jumlah siklus**: statistik online
  Welford, min/max per fase, slope berbobot indeks dan
  agregasi antarsiklus; **tidak menyimpan 900×10 ADC**.
- Semua 30 fitur mengikuti urutan asli `scripts/svm30_embedded_features.py`.
  ADC absolut: **tanpa baseline t0 correction**.
  `std` adalah population std (`ddof=0`), slope purging
  regresi pada 25 titik, slope collecting pada 5 titik,
  AUC adalah **jumlah lima ADC**, bukan trapezoid.
- Strict state machine menolak 5 siklus, data kurang,
  out-of-order, fase salah, sampel duplikat, dan ADC rusak.
  `copyFeatures` gagal sebelum 900 sampel lengkap.
- **199/199 vektor 30 fitur lulus uji toleransi** terhadap
  NumPy float64: max selisih absolut **0,0229167** dalam
  satuan masing-masing fitur, max selisih relatif **5,78117×10⁻⁵**.
  Gate per nilai: `abs_error <=0.05` **atau**
  `relative_error <=0.003`; hasil aktual jauh lebih baik.

## B3 — Model SVM float32 PROGMEM / native / AVR (PASS)

- `scripts/export_svm30_for_avr.py` mengecek SHA bundle
  terlebih dahulu sebelum deserialize joblib. Header ekspor
  berisi parameter model pengguna; **disimpan privat dan
  tidak dipush**, di `private/embedded_svm30_model.h`.
- SHA256 header yang terverifikasi:
  `3c4589bb6d5b95b8eb20892adfebc45728d28f7abe00041a90baf0893851426b`.
  Hasil ekspor **identik byte-per-byte** pada sklearn 1.7.2
  dan 1.9.0.
- `src/embedded_svm30_classifier.h/.cpp` mengaplikasikan
  StandardScaler *training-fitted* di PROGMEM, menghitung
  **125 kernel RBF** sekali, lalu melakukan multiclass
  libsvm one-vs-one menggunakan `dual_coef_`,
  `intercept_` dan tie-break sesuai urutan kelas.
  Model tidak dialokasikan ke SRAM.
- Kesetaraan pada **199/199 prediksi kelas** = **0 mismatch**.
  Nilai tiga *pairwise decision scores* juga cocok dengan
  referensi float64: max selisih absolut
  **3,6055×10⁻⁶**. Margin absolut terkecil ke
  batas keputusan pada corpus: **0,0014201**;
  tidak ada pembalikan kelas pada 199 corpus.
- Native negative tests: **10 sesi tidak valid ditolak**
  tanpa menebak label; test status/reset/fault/wrong input
  pada objek `Features` PASS.
- `pio run -c scripts/platformio_svm30_bench.ini
  -e svm30_avr_compile`: **PASS**, model dan
  class C++ berhasil dikompilasi AVR 16MHz,
  **Flash 22.356 / 253.952 bytes,
  SRAM global 431 / 8.192 bytes**, pada *program uji
  terisolasi* bukan firmware utama.
- `avr-nm` menunjukkan `kSVectors` **15.000 bytes**
  dan `kDualCoef` **1.000 bytes** berada di
  **Flash** (simbol tipe `t`), bersama
  scaler mean+scale 240 bytes.
  Objek fitur uji `featureState` memakai **416 bytes
  SRAM** di bss. Ini **bukan** pengukuran stack runtime.
- Build utama `pio run -e mega2560` tetap **PASS**:
  **Flash 34.760 bytes / SRAM global 3.899 bytes**,
  tidak berubah. Feature flag `ENABLE_AVR_SVM30=1`
  hanya di lingkungan uji; firmware normal tetap
  **tidak menjalankan SVM**.

## Komponen dan cara mengulang tes

Model joblib harus tersedia di lokal/diunduh dari sumber pemilik,
**tidak dari GitHub**. Jangan memakai file random berformat
`joblib`; format pickle memiliki risiko eksekusi kode.
Jangan publikasi `private/` berisi koefisien/vectors.

```powershell
# Dari root repository, dengan path model milik tim:
python scripts/export_svm30_for_avr.py --bundle "$env:USERPROFILE\Downloads\final_svm.joblib" --out private/embedded_svm30_model.h --manifest private/embedded_svm30_manifest.json

# Native unit tests dan parity (contoh Windows + MSYS2 g++):
g++ -std=c++11 -O2 -Wall -Wextra -Werror -DENABLE_AVR_SVM30=1 src/embedded_svm30_features.cpp src/embedded_svm30_classifier.cpp tests/embedded_svm30_native.cpp -o private/svm30_native.exe
private\.venv_svm_reference\Scripts\python.exe scripts/test_embedded_svm30_parity.py --bundle "$env:USERPROFILE\Downloads\final_svm.joblib" --helper "$env:USERPROFILE\Downloads\predict_roast_svm.py" --binary private/svm30_native.exe --output private/svm30_golden_scores_full199.json --limit 199
python scripts/test_embedded_svm30_negative.py --binary private/svm30_native.exe
python scripts/test_embedded_svm30_exporter.py

# AVR compile-only (BUKAN upload):
pio run -c scripts/platformio_svm30_bench.ini -e svm30_avr_compile
pio run -e mega2560
```

Jika output private golden telah ada, pilih **nama output baru**
agar audit historis tidak tertimpa.

## Batas dan langkah berikutnya

1. **B0 masih BLOCKED**: PCB dan Nextion fisik tetap perlu
   pemulihan startup `Initializing Systems`, bersama gangguan
   USB xHCI yang sebelumnya terjadi.
2. **B4 NOT DONE**: akumulator SVM belum dihubungkan ke
   `adsCallback()`, `startAcquisition()` atau hasil
   `pResult` firmware utama; belum ada firmware standalone
   berfungsi penuh yang siap flashing.
3. **B5 NOT DONE**: perlu pengukuran stack, waktu 125 `expf`
   di ATmega 16MHz, pengujian integrasi timer/I²C/Serial2
   dan fail-safe berbasis aktuator.
4. **B6 NOT DONE**: tidak ada flashing atau pengujian fisik.
   Akurasi model pada kopi baru tidak bisa disimpulkan dari
   keberhasilan parity test.
