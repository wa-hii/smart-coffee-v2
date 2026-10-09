# Kondisi Aktual Smart Coffee E-Nose v2 — audit Tahap 0–1, 9 Oktober 2026

> Sumber acuan: kode sumber, hasil QA offline, dan CSV mentah B32–B35 pada direktori utama. Dokumen ini mencatat keadaan rekayasa yang telah diperiksa, **bukan bukti pengujian perangkat fisik secara langsung**.

## 1. Repositori dan ruang lingkup

- Repositori kerja: smart-coffee-v2-hardware/smart-coffee-v2-hardware, branch **wahyu**. Baseline awal audit independen 8 Oktober adalah **54d3321**; baseline sebelum audit Tahap 0 tanggal 9 Oktober adalah **bf7080e**. Perubahan lokal `platformio.ini` untuk COM5 tetap milik pengguna dan tidak dimasukkan ke commit.
- Firmware utama ATmega2560 berada di **src/**. Proyek HMI Nextion yang menjadi acuan adalah **nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI**. Aset desain Figma telah dikunci; berkas TFT lama belum terbukti identik dengan HMI terbaru.
- Urutan sensor pada firmware dan CSV: TGS822, MQ135, **MQ3**, TGS2611, TGS2620, TGS2600, TGS2602, MQ8, TGS813, TGS816. Empat ADS1115 menggunakan alamat 0x48–0x4B; SHT30 dibaca melalui bus I2C.
- Nextion: USART2 (`Serial2`) 9600 baud, yaitu PH0/RXD2 pada **pin TQFP-100 nomor 12** (RX2/D17 pada header Arduino Mega) dan PH1/TXD2 pada **pin nomor 13** (TX2/D16). Angka pin IC 8/9 pada dokumen lama keliru menurut datasheet Microchip. Serial USB ke komputer/host menggunakan 115200 baud. Koreksi belum diverifikasi pada skematik PCB fisik.
- Akuisisi aktif: **5 siklus × (purging 25 detik + collecting 5 detik)**, dengan durasi nominal sekitar 150 detik per pengujian. Keterlambatan antarmuka/komunikasi dan durasi nyata masih harus diukur.

## 2. Kondisi dan kesiapan subsistem

| Subsistem | Bukti yang telah diperiksa | Hal yang belum dibuktikan |
|---|---|---|
| Firmware utama ATmega | Kompilasi PlatformIO mega2560 berhasil. RAM statis 3.720/8.192 byte dan flash 35.854/253.952 byte pada saat pemeriksaan. | Pembacaan sensor fisik, ketepatan waktu, stack/heap runtime, pemanasan sensor, kalibrasi, dan keselamatan aktuator. |
| Firmware uji Nextion | Kompilasi environment nextion_test berhasil. | Pertukaran UART nyata, pemulihan koneksi, dan penanganan galat perangkat. |
| HMI | Pemeriksa offline berhasil untuk 12 aset Figma, 12 halaman HMI, 23 event yang dipetakan, serta kontrak komunikasi. | Kompilasi Nextion Editor, simulasi editor, TFT terbaru, dan layar fisik. |
| Akuisisi | 86 dari 86 CSV B32–B35 lolos validator struktur. | Keakuratan kalibrasi ADC/sensor, timestamp nyata, dan identitas spesimen/sesi. |
| Ekstraksi fitur | Kandidat 62 fitur dengan 86 observasi tingkat file berhasil dibuat tanpa training. | Seleksi fitur ilmiah, uji generalisasi, dan kesesuaian fitur ketika inferensi. |
| Model AI | Laporan historis Random Forest B01–B05 tersedia. | Evaluasi, pemilihan, serta validasi model pada B32–B35. |
| Raspberry Pi 5 | Menjadi target integrasi yang direncanakan. | Implementasi adapter, benchmark pada Pi, dan komunikasi inferensi dua arah. |

**Audit Tahap 0 (9 Oktober):** baseline lintas modul dicatat di `docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`. Script `scripts/test_stage0_contract.py` memeriksa konstanta fase, kanal ADC, format serial/CSV, sumber HMI, pemetaan preset antar-kolektor, serta pemetaan pin Nextion tanpa mengakses COM5. Opsi UART `Serial1` ke Raspberry Pi masih rancangan, bukan jalur yang telah dipasang atau aktif.

## 3. Inventaris dataset B32–B35

- Total **86 berkas**: B32 = 18; B33 = 20; B34 = 22; B35 = 26.
- Total **13.615 baris CSV**: **13.003 baris sensor lengkap** serta **612 baris event historis yang hanya berisi metadata**. Tidak ditemukan baris sensor parsial menurut validator struktural.
- Distribusi fase: **10.756 baris purging** dan **2.247 baris collecting**.
- Tidak ditemukan nilai suhu atau kelembapan yang hilang pada himpunan data ini. Tidak ditemukan sel ADC bernilai 0 atau 32767.
- Distribusi file berdasarkan tingkat roasting: light = 30; medium = 28; dark = 28. Ditemukan **23 kombinasi kode sampel roast–origin**.
- Secara nominal terdapat 430 kelompok siklus (86 × 5), **bukan 430 spesimen kopi fisik yang independen**. Beberapa file B35 dengan akhiran timestamp adalah pengukuran tambahan; independensinya belum diketahui.
- Field timestamp berasal dari **millis() ATmega**, yakni waktu sejak MCU menyala, bukan tanggal dan jam kalender. CSV aktif belum menyertakan ID spesimen fisik, ID sesi atau tanggal pengukuran yang eksplisit.
- Definisi identitas origin perlu dibakukan, terutama kode **TEM/MUK** yang memiliki variasi nama pada metadata historis.

## 4. Temuan prioritas

1. **P0 — Integritas CSV.** Listener lama memasukkan event PHASE_CHANGE sebagai baris CSV kosong. Bug utama sudah diperbaiki dalam commit 54d3321. Audit lanjutan menambah validasi bilangan dan rentang ADC, deteksi indeks duplikat, perlindungan benturan nama file, serta regression test.
2. **P0 — Ketidakcocokan ekstraktor historis.** scripts/8_extract_features.py memakai MQ9 dan membutuhkan minimal 10 titik collecting; data aktif memakai MQ3 dengan sekitar 5 titik. Skrip historis kini menolak pencampuran skema dan tidak menimpa artefak lama. Ekstraktor kandidat MQ3 dibuat terpisah.
3. **P0 — Validitas evaluasi AI.** Random Forest B01–B05 sebelumnya menghasilkan akurasi uji 57,50% (baseline) dan 55,00% (tuned). Angka tersebut tidak berlaku untuk B32–B35. Cross-validation lama menggunakan StratifiedKFold pada run yang berkorelasi, sehingga skor CV lama belum dapat dijadikan bukti evaluasi bebas data leakage.
4. **P1 — Risiko salah atribusi fase.** adsCallback() membaca sensor sebelum processAcquisitionState() mengganti fase, tetapi mengirim JSON sesudahnya. Sampel tepat di batas fase mungkin diberi label fase yang baru. **Belum diubah**, karena perlu bukti timing melalui simulasi dan pengujian perangkat.
5. **P1 — Status AI perangkat.** Inferensi TinyML ATmega dinonaktifkan secara bawaan (USE_ON_DEVICE_INFERENCE=0); origin dan confidence tampil N/A. Jalur hasil inferensi dari Pi belum tervalidasi.
6. **P1 — Metadata dan protokol.** Event saat ini belum memiliki identitas akuisisi unik, identitas spesimen fisik, waktu kalender, sequence/acknowledgment, serta kontrak hasil dan error host yang terversi.
7. **P0 — Keselamatan diagnostik pin dan UART mendatang.** Perintah `#pin_scan;` mencakup D19/RX1 serta D20/SDA dan berpotensi mengganggu sambungan Pi atau bus sensor bila digunakan saat terhubung. Jangan menjalankan perintah ini sebelum ditinjau dan memiliki SOP.
8. **P0 — Label pada mode AI_TEST.** Event `ACQ_START` pada `ai_test` masih menyertakan pilihan roast/origin yang merupakan metadata default UI, bukan ground truth; listener saat ini tidak menyimpannya sebagai dataset labeled. Harus dipisahkan dalam kontrak inferensi mendatang.
9. **P0 — Keputusan label origin.** Pemetaan preset yang sama antarkolektor cocok pada kode yang beririsan, tetapi daftar preset tidak identik. Label TEM/MUK/CAW belum dibakukan berdasarkan definisi kopi nyata.

### Implementasi lanjutan Tahap 1 — 9 Oktober 2026

- **Pengamanan offline diterapkan:** `#pin_scan;` tidak lagi menjalankan pemindaian GPIO; `#valve_on/off/test;` dinonaktifkan secara bawaan (`ENABLE_MANUAL_ACTUATOR_TESTS=0`), dan hanya boleh diaktifkan untuk SOP bench. `#start;` serial membutuhkan seluruh ADC tersedia; `#scan;` I2C diblokir ketika akuisisi berlangsung.
- **Mode AI_TEST:** `ACQ_START` sekarang tidak mengeluarkan `sample_id`, `roast_level`, `origin_code`, `batch_id` atau `filename`. Untuk mode `labeled_data`, metadata tetap dikeluarkan agar listener lama kompatibel.
- **Urutan sampling:** `adsCallback` mengirim frame sensor ketika fase aktif **sebelum** mengubah fase dan mengirim `PHASE_CHANGE`/`ACQ_COMPLETE`. Frame idle/paused tidak diterbitkan sebagai sampel. Pada simulasi 1 Hz ideal jumlahnya 150 sampel (125 purging, 25 collecting), tetapi kondisi waktu dan kualitas sinyal fisik belum dibuktikan.
- **Regresi:** pemeriksaan kontrak firmware baru serta tes listener untuk AI_TEST tanpa label, COMPLETE ganda, dan STOP parsial ditambahkan. Detail: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`.

**Status Tahap 1: perbaikan offline telah diimplementasikan, verifikasi hardware belum dilakukan.** Narasi risiko sebelumnya adalah kondisi *sebelum perbaikan*, bukan indikasi bahwa perbaikan kode belum dikerjakan.

## 5. Batas pemeriksaan dan keputusan

Yang dilakukan: kompilasi offline, pengujian parser/validator, pengecekan kontrak HMI, dan analisis berkas CSV yang tersedia. Tidak ada akses COM5, restart listener, penulisan EEPROM, kalibrasi, penggerakan pompa, flashing, training model, maupun deployment Raspberry Pi.

**Keputusan:** kesiapan perangkat lunak untuk pemrosesan CSV secara struktural cukup baik; klaim generalisasi AI maupun E2E perangkat fisik **belum terpenuhi**. Fitur baru berstatus kandidat penelitian, bukan model siap deployment. Inventaris Tahap 0 telah diperbarui dengan sumber acuan dan pemilik masing-masing masalah terbuka; Tahap 1/2/7/9 tetap memiliki pekerjaan yang wajib dibuktikan.

Dokumen lanjutan:

- **01_MASTER_E2E_ROADMAP.md** — peta jalan utama.
- **02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md** — baseline, koreksi pin, dan daftar keputusan terbuka.
- **03_AI_MODEL_RESEARCH_AND_EVALUATION.md** — penelitian dan metodologi AI.
- **04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md** — rancangan integrasi.
- **06_INDEPENDENT_AUDIT_QA_QC.md** — temuan audit serta bukti pengujian.
