# Rencana Backup: Smart Coffee E-Nose Standalone (ATmega2560 + Nextion)

**Tanggal rencana:** 11 November 2026

**Cabang kerja:** `wahyu`

**Status:** **RANCANGAN TEKNIS + FEASIBILITY SOURCE**, belum ada model tertanam/flash ke MCU atau pengujian Nextion fisik.
**Kebutuhan pengguna:** saat USB Raspberry Pi–PCB bermasalah, sistem tetap dapat menjalankan **sensor → fitur → AI embedded → hasil roasting di Nextion**, tanpa Raspberry Pi dan tanpa penyimpanan CSV untuk sementara.

## Keputusan arsitektur

**Mode backup independen Pi:** Nextion (tombol `START AI TEST`) → ATmega2560 (akuisisi 30 siklus, sensor ADS1115, kendali valve) → **akumulator fitur SVM** → **inferensi SVM pada AVR** → Nextion `pResult`.

- Nextion tetap melalui **Serial2 ATmega @9600 baud**.
- Sensor tetap dibaca sesuai mapping hardware sekarang, 30 siklus × (25 detik purging + 5 detik collecting) = **900 pembacaan 1 Hz / 15 menit nominal**.
- Pompa/dinamo adalah hardware yang berjalan terus pada sistem yang dijelaskan pengguna; **valve solenoid tidak diaktifkan pada IDLE**, hanya collecting. Jangan mengubah logika aktuator sebagai bagian porting AI.
- Tidak perlu Raspberry Pi, Wi-Fi, MQTT, USB listener, CSV, SD card, database, atau pencatatan riwayat persisten. Kelas tampil **langsung melalui UART Nextion** setelah AI Test selesai.
- Pada backup, **mode Take Data tidak menghasilkan CSV tanpa host**. Untuk mencegah kesan seolah data tersimpan, tampilkan pesan tidak tersedia / nonaktifkan START Take Data pada profil standalone (tanpa mengganti tampilan visual).
- Model dipakai **hanya untuk prediksi roasting Light/Medium/Dark**. Belum ada model origin. `tOrigin`, `tOConf` dan `tRConf` tetap `N/A` sampai tersedia validasi confidence; jangan mengaku probabilitas terkalibrasi.
- Profil standalone harus **opt-in pada waktu build** dan tetap disabled pada firmware standar; jangan mengganti RF / Pi production flow secara diam-diam.

## Model yang dipertahankan (bukan SVM 9 fitur)

Artefak utama dari **enam berkas SVM final pengguna**:

- `final_svm.joblib`, SHA256 `d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33`.
- Metadata `final_svm_info.json`: SVC, RBF, `C=1`, `gamma=0.1`, **30 fitur**, **176 sesi train** menurut metadata, kelas `dark`, `light`, `medium`, nested-CV weighted accuracy **85,23%** dan macro-F1 **82,23%** menurut metadata (**belum direproduksi dan belum blind**).
- Bundle joblib diperiksa di lingkungan offline: `model`, `scaler`, `feature_names`, `feature_indices`, `classes`; support vectors **125**, kelompok `[44,34,47]`; `support_vectors_.shape=(125,30)`, `dual_coef_.shape=(2,125)`, `intercept_.shape=(3,)`, standard scaler 30 mean dan scale.
- `predict_roast_svm.py` adalah **acuan rumus asli**. Pembacaan pada helper toleran terhadap CSV yang tidak lengkap (sebagian error diabaikan), sehingga *implementasi standalone harus lebih ketat*: tepat 900 data valid, urutan fase/indeks dan semua kanal wajib yang dibutuhkan model valid.
- Model `final_svm_maybe.joblib` dan analisis `maybe` adalah eksperimen lain, **tidak digunakan** untuk firmware cadangan. SVM 9 fitur/133 sesi di staging Pi juga **bukan** model yang dipilih pada rencana ini.

### Kontrak fitur 30 dimensi — wajib identik dengan training

Urutan fitur disimpan pada `scripts/svm30_embedded_features.py`; 30 nama harus sesuai `bundle['feature_names']` tanpa permutasi. Sumber sensor untuk model hanya **TGS822, TGS2602, TGS816, MQ8**, meskipun firmware dapat tetap membaca 10 sensor agar kompatibel dengan arsitektur awal.

Fitur terdiri dari statistik ADC **absolut** (tidak dikurangi baseline t0/per-siklus), termasuk:

- Statistik collecting per siklus: `max`, `mean`, `std` populasi, `min/max delta`, `early/late/plateau`, `AUC=sum(5 sampel)`, `slope_rise`, `rel_response=(max-first)/(abs(first)+1e-6)`.
- Statistik purging per siklus: `mean`, `min`, `std` populasi, dan `slope` linear least squares selama 25 pembacaan.
- Agregasi antarsiklus: *mean* dan *population standard deviation* (`ddof=0`) selama 30 siklus; `global_range` pada 150 nilai collecting yang relevan.
- Pada rekaman 5 detik collecting, `early_mean`, `late_mean`, `plateau_mean` dan `mean_mean` dapat bernilai identik secara matematis. **Jangan menghapus fitur redundan** tanpa model baru; urutan/skalanya adalah bagian kontrak model 30 dimensi.
- **Beda dengan eksperimen 9 fitur lama:** tidak memakai baseline subtraction lokal, tidak membuat 9 input SVM, dan tidak meng-fit scaler pada satu sesi AI Test.

## Bukti awal kelayakan memori

Sumber resmi Microchip menyatakan ATmega2560 memiliki **256 KB Flash dan 8 KB SRAM**. Environment PlatformIO `mega2560` membatasi ruang aplikasi 253.952 byte. Compile-only 11 November terhadap firmware saat ini **PASS**:

| Penggunaan | Sebelum embedded SVM | Catatan |
|---|---:|---|
| Flash program | **34.760 / 253.952 byte** | Masih banyak ruang, belum termasuk kode SVM |
| SRAM global/static | **3.899 / 8.192 byte** | Sisa 4.293 byte **termasuk stack runtime** |
| Support vectors | 125 × 30 × 4 = **15.000 byte** | Wajib **Flash/PROGMEM**, jangan disalin ke RAM |
| Dual coefficients | 2 × 125 × 4 = **1.000 byte** | PROGMEM |
| Scaler mean + scale | 2 × 30 × 4 = **240 byte** | PROGMEM |
| Intercept | 3 × 4 = **12 byte** | PROGMEM |
| Total model numerik (perkiraan) | **16.252 byte Flash** | Belum termasuk fungsi inferensi / overhead / metadata |

**Keputusan sementara:** model tampak **layak ditampung di Flash** ATmega2560, tetapi **kelayakan SRAM, stack dan latensi tetap harus diuji di build/simulator lalu hardware**. `double` AVR pada toolchain ini adalah 32-bit; hasil operasi tidak identik persis dengan NumPy float64. Semua array model menggunakan `PROGMEM` + akses `pgm_read_float`, bukan array global SRAM.

## Milestone implementasi (urut, dengan kondisi lulus)

### B0 — Kembalikan fungsi boot/Nextion sebelum AI

1. **Hentikan G2/G3 USB**: terakhir `/dev/ttyUSB0` hilang dan Pi melaporkan `xHCI host controller not responding; HC died`.
2. Kondisi fisik: pompa/dinamo hidup normal; valve solenoid diam pada IDLE. Nextion **stuck `Initializing Systems`**, **belum berfungsi**. Ini harus dibedakan dari persoalan model AI.
3. Periksa catu daya, ground, VBUS/backfeed USB–FT232, kestabilan I²C ADS1115 dan UART2 Nextion. Uji startup MCU terisolasi dari Pi **setelah power-off aman dan SOP**.
4. Evaluasi boot source `scanI2C()` dan `sensors.begin()` agar kegagalan sensor/I²C tidak menahan `pHome` tanpa batas; lakukan perubahan setelah diagnosis, dengan timeout/fail-safe.
5. **Gate B0 PASS:** papan dapat boot `pSplash → pHome` stabil tanpa USB/Pi, tetap pada kondisi idle aman. Jangan flash AI sebelum ini dibuktikan.

### B1 — Bekukan model dan buat golden reference

1. Pin SHA256 **final SVM** dan versi serialisasi asli scikit-learn 1.7.2. Muat joblib **hanya di lingkungan development terisolasi** dari file yang dipercaya.
2. Gunakan `predict_roast_svm.py` untuk membuat vektor referensi 30 fitur (urutan sama dengan `feature_names`), `scaler.transform()` serta kelas `SVC.predict()` untuk CSV lengkap.
3. Simpan manifest sumber + hash dan output test tanpa mengubah CSV. **Tolak** 5-siklus, ADC hilang, nilai NaN, urutan phase/index salah, dan data berlabel yang bocor ke `AI_TEST`.
4. Gunakan hasil pada **rekaman lengkap lintas L/M/D**; semua pengulangan dari satu spesimen tidak boleh diperlakukan sebagai sampel fisik independen.
5. **Gate B1 PASS:** Python golden vectors 30 fitur dan prediksi disimpan/terverifikasi; fitur disepakati persis.

### B2 — Implementasi ekstraksi fitur secara streaming di ATmega

1. Buat modul `EmbeddedSvmFeatureAccumulator` terpisah, menerima `sample(sensor_adc, phase, cycle, sample_idx)`; tidak boleh mengambil roast label saat AI Test.
2. Gunakan **satu siklus dalam memori** atau statistik online (Welford mean/variance, running min/max, slope sum) untuk 4 sensor terkait, kemudian agregasi mean/std antarsiklus. Jangan simpan 900 × 10 ADC di RAM.
3. Pastikan statistik populasi `ddof=0`, rumus slope purging 25 titik dan collecting 5 titik sama dengan NumPy/Polyfit, `AUC_mean` sama dengan penjumlahan ADC, bukan luas trapesium.
4. Integritas: hitung tepat **30 × 25 purge + 30 × 5 collect = 900 samples**; abort/cancel/timeout/restart wajib reset akumulator dan menghasilkan `N/A`.
5. **Gate B2 PASS:** seluruh 30 fitur MCU cocok dengan Python golden test dengan toleransi yang ditetapkan dari pengujian numerik (termasuk fitur mendekati nol).

### B3 — Ekspor SVM RBF ke Flash / prediksi C++ native dan AVR

1. Skrip awal yang **sudah ada tetapi belum menjadi firmware deploy**: `scripts/export_svm30_for_avr.py`, yang memeriksa SHA dan menghasilkan parameter 125 SV `float32` di `PROGMEM`. **Jangan timpa atau commit header berisi koefisien model privat** tanpa review.
2. Implementasikan StandardScaler MCU: `x_scaled = (x_raw - mean_train) / scale_train` **tanpa refit**.
3. Implementasikan kernel `exp(-0.1 × sum((x_scaled - support_vector)^2))` untuk 125 SV; klasifikasi multiclass memakai **libsvm one-vs-one vote dengan posisi kelas dan koefisien `dual_coef_` yang benar**. Tidak cukup mengambil `argmax(decision_function)` tanpa menyesuaikan semantik `sklearn.SVC.predict()`.
4. Gunakan keluaran kelas `dark|light|medium` sesuai urutan model; jaga *tie-breaking*, float32, bilangan tidak hingga, dan output `N/A` pada invalid.
5. **Gate B3 PASS:** tes C++ native membandingkan keluaran perhitungan kernel/skor/kelas dengan sklearn; selisih prediksi mendekati ambang ditinjau, target **nol salah klasifikasi terhadap corpus referensi golden**, atau fail-closed (bukan diam-diam menebak).

### B4 — Integrasi firmware tanpa Pi, storage, atau perubahan desain Nextion

1. Buat **profil build standalone** sendiri; **jangan sentuh `platformio.ini` pribadi yang saat ini dirty**, COM port, atau source proyek HMI. Build default tetap sebagai rollback.
2. Di `main.cpp`, saat `AI_TEST` mulai: `inference.reset()` / `svm.reset()`, fase 25/5 tetap, komputasi streaming berjalan sesuai ADC callback (1 Hz). Hindari operasi eksponensial saat sampling; lakukan inferensi **setelah pengukuran lengkap**.
3. Tidak perlu menyalakan listener Pi, menulis CSV, atau memancarkan JSON sensor 900 kali ke USB; matikan *host sensor stream* pada profil standalone untuk mencegah buffer serial memperlambat proses.
4. `pHome → pTest → pTestRun → pResult`. Pada selesai 30 siklus: tampilkan `tRoast` = `LIGHT/MEDIUM/DARK`. Jika ada kesalahan sensor/fitur/model/timeout: `N/A`, beserta `pAlert` sesuai event yang tersedia. Origin/Confidence tetap N/A.
5. Sesi baru/cancel/error membersihkan prediksi lama. Mode `Take Data` ditandai **tidak tersedia tanpa host**, bukan pura-pura menyimpan CSV. UI visual tetap sama.
6. **Gate B4 PASS:** tidak ada dependensi Raspberry Pi, USB, network, file; seluruh event Nextion valid, label tidak bocor, halaman `pResult` terisi saat skenario simulated 30-cycle valid.

### B5 — QA performa dan keandalan sebelum flashing

1. Compile-only `pio run` pada profil standalone; ukur Flash/SRAM global serta cek stack menggunakan watermark; pastikan ruang stack aman saat *worst case* dan tidak terjadi korupsi.
2. Ukur **latensi `SVC.predict()` MCU** dan konsumsi RAM pada 125 kernel RBF (125 operasi `expf` dan 3.750 operasi jarak kuadrat). Tidak boleh menghambat ADC, timer, UART Nextion, atau aktuator.
3. Test negatif: ADC missing/korup, data incomplete, boot splash, reset saat sesi, valve fail-safe, stop/cancel, salah urutan fase, floating invalid, skor margin rendah, stuck I²C.
4. Bentuk **firmware binary + checksum + rollback** untuk image sebelumnya; jangan menulis EEPROM R0 saat upload/boot biasa.
5. **Gate B5 PASS:** unit+native equivalence, PlatformIO build, regression firmware, Nextion contract, memory/stack/latency evidence; operasi hardware belum dijalankan tanpa SOP.

### B6 — Pengujian supervised di perangkat fisik

1. Setelah B0 dan SOP hardprog selesai, backup firmware existing/EEPROM dan flash lewat jalur ISP/USB yang **telah dibuktikan aman**. Kegagalan xHCI Pi lama bukan alasan untuk memaksa upload.
2. Boot tanpa Pi, verifikasi startup `pSplash→pHome`, LED/valve aman, ADC sensor tersedia.
3. Uji `START AI TEST` **30 siklus / 15 menit** dengan kopi yang tidak digunakan saat training, dan hasilnya muncul di `pResult`; periksa waktu dan respons keselamatan.
4. Uji beberapa roast/origin/perangkat dan *unknown* bila punya SOP; **akurasi di perangkat belum boleh diklaim berdasarkan metadata nested CV**.
5. **Gate B6 PASS** hanya ketika hasil Light/Medium/Dark benar-benar tampil di Nextion fisik secara mandiri **tanpa Raspberry Pi**, serta ada evidence validasi dan prosedur rollback.

## Kriteria keputusan

**Pilihan A (diutamakan):** port **SVM 30 fitur/125 support vector yang sama** ke Flash dengan inferensi C++ float32, tanpa melatih ulang. Layak secara perkiraan kapasitas; akurasi ekuivalensi **masih harus dibuktikan**.

**Pilihan B (fallback jika latensi/RAM tidak memenuhi):** lakukan kompresi/quantization dengan verifikasi perubahan hasil prediksi atau *distillation* menjadi model kecil. **Membutuhkan validasi ulang** dan tidak dapat mengklaim skor 85,23% tanpa pengujian baru. Hindari otomatis mengganti menjadi SVM 9 fitur (berbeda metodologi/hasil).

**Prioritas kerja:** **B0 startup hardware → B1 golden reference → B2 fitur streaming → B3 exporter+SVM libsvm → B4 Nextion → B5 compile/QA → B6 bench hardware**. Tahap B1–B5 bisa disiapkan offline sembari B0 ditangani hardware; **tidak perlu terhubung ke Raspberry Pi untuk sistem standalone pada saat digunakan**.

## Bukti yang ada dan belum ada

**Sudah diverifikasi:** struktur dan hash model final pengguna, feature order, 125 SV, ukuran baseline firmware 34.760B Flash dan 3.899B SRAM saat compile-only, workflow HMI/Nextion dalam source serta kegagalan USB xHCI dan splash stuck yang terdokumentasi.

**Belum dilakukan:** mengekspor header privat produksi, modul fitur streaming AVR, C++ libsvm inferensi, pengujian kesetaraan 30 fitur/prediksi, compile firmware standalone lengkap, upload ke PCB, pengujian Nextion fisik. **Rencana ini tidak boleh dilaporkan sebagai implementasi selesai.**
