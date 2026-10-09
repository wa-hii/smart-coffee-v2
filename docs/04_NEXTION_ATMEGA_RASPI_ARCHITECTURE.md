# Rancangan Integrasi Nextion–ATmega2560–Raspberry Pi 5

**Status: rancangan teknis, belum diterapkan pada perangkat fisik.** Audit Tahap 0 pada 9 Oktober 2026 mencatat opsi UART GPIO terpisah sebagai alternatif yang sedang dipertimbangkan; belum ada perubahan protokol komunikasi, kabel atau deployment. Lihat `02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`.

## 1. Arsitektur saat ini dan target

**Arsitektur saat ini:** Sepuluh kanal sensor gas → empat ADS1115 → ATmega2560. Sensor SHT30 menggunakan **bus I2C langsung**, bukan melewati ADS1115. ATmega mengendalikan pompa, valve, dan Nextion melalui Serial2 @ 9600 baud; Serial USB @ 115200 baud mengirim event serta pengukuran JSON ke komputer. Opsi inferensi TinyML lokal tidak aktif secara bawaan; hasil origin/confidence berstatus N/A.

**Arsitektur target yang direkomendasikan (hybrid):**

    Nextion START TEST
      → ATmega2560 (kontrol perangkat dan akuisisi)
      → transport serial (USB aktif saat ini / UART1 kandidat)
      → Raspberry Pi 5 (validasi dan penyusunan sesi)
      → Preprocessing dan ekstraksi fitur
      → Model AI terverifikasi
      → Keputusan prediksi / unknown
      → transport serial yang telah disepakati (hasil dan acknowledgment)
      → ATmega2560
      → Nextion pResult

Inferensi tidak boleh menghalangi mekanisme keselamatan pompa, valve, dan pengaturan waktu pada ATmega. Raspberry Pi merupakan lapisan pemrosesan AI, bukan pengendali utama keselamatan perangkat. Jika USB terputus, model tidak ditemukan, timeout, atau data tidak valid, layar harus menampilkan kesalahan atau **N/A**, bukan hasil tebakan.

## 2. Pembagian tanggung jawab

| Komponen | Tanggung jawab utama | Bukan tanggung jawabnya |
|---|---|---|
| **ATmega2560** | Baca ADC/SHT30, kontrol aktuator, state machine, waktu akuisisi, keselamatan perangkat, event, komunikasi Nextion | Training model, penyimpanan data besar, fitting preprocessing |
| **Nextion** | Interaksi pengguna, pemilihan metadata untuk AMBIL DATA, progres, status, hasil dan error | Menetapkan ground truth pada AI_TEST atau menjalankan model AI |
| **Raspberry Pi 5** | Menerima serial, memvalidasi payload, mendeteksi data hilang, menyusun lima siklus, ekstraksi fitur, inferensi, unknown/N/A, log dan riwayat | Mengendalikan pompa/valve secara langsung |
| **Komputer training offline** | Inventaris dataset, validasi kelompok, eksperimen model, pemilihan fitur, ekspor artefak terverifikasi | Melakukan fitting otomatis pada data pengujian saat perangkat berjalan |

## 3. Usulan kontrak serial host versi 1 — belum diimplementasikan

Format yang disarankan: pesan **JSON UTF-8 per baris (NDJSON)** dengan field version=1, type, session_id (UUID), message_seq (urutan pesan dalam sesi), device_id, emitted_uptime_ms, dan mode.

| Jenis pesan | Fungsi dan field utama |
|---|---|
| **ACQ_START** | Menandai mode labeled_data atau ai_test; memuat jumlah siklus/durasi purging/collecting dan versi firmware/skema. Label hanya boleh digunakan pada labeled_data. |
| **SENSOR_SAMPLE** | Membawa nomor siklus, fase, sample_idx, seluruh 10 ADC, suhu/kelembapan opsional dan kode kualitas. |
| **PHASE_CHANGE / ACQ_PAUSE / ACQ_RESUME / ACQ_STOP / ACQ_COMPLETE** | Perubahan status serta jumlah sampel; event tidak pernah dihitung sebagai baris sensor. |
| **INFERENCE_REQUEST** | Permintaan model setelah lima siklus AI_TEST valid dan lengkap. |
| **INFERENCE_RESULT** | session_id yang sama, versi model, prediksi atau unknown, probabilitas terkalibrasi bila tersedia, tanda kualitas dan hash artefak. Origin dapat unknown walaupun roast terprediksi. |
| **INFERENCE_ERROR** | Kesalahan data/sesi/model/skema, perangkat host tidak tersedia, atau timeout. ATmega menampilkan N/A dan alasan. |
| **ACK / NACK** | Konfirmasi nomor pesan dan sesi; pengiriman ulang hanya untuk operasi idempoten, **bukan** memulai kembali pengambilan data fisik secara otomatis. |

Nama dan field di atas adalah **usulan desain**, belum merupakan pesan yang benar-benar dikeluarkan firmware. **Perubahan Tahap 1 (9 Oktober):** firmware sekarang menghilangkan label pilihan layar dari event `ACQ_START` ketika mode `ai_test`; mode `labeled_data` tetap memuat label untuk autosave CSV. `session_id`, `message_seq`, ACK/NACK, dan hasil AI dari Pi belum tersedia. Bedakan dengan jelas **run_id** (siklus ke-1 s.d. ke-5), **session_id** (satu pengambilan data), **sample_id** (kode label), serta **ID spesimen fisik** (kopi yang sama mungkin diuji berkali-kali).

### Pilihan transport yang perlu diputuskan

| Opsi | Kondisi aktual dan prasyarat |
|---|---|
| **USB Serial** | **Sudah aktif** untuk komputer/laptop melalui `Serial` @ 115200. Bisa menjadi jalur host Pi jika perangkat USB dan kepemilikan port memungkinkan. Tidak sama dengan UART GPIO langsung. |
| **UART khusus ke Pi** | **Belum diterapkan.** Kandidat `Serial1` ATmega: TX1 D18/PD3 dan RX1 D19/PD2; Nextion tetap `Serial2`. Ke GPIO Raspberry Pi 5 diperlukan pengubah level logika 5 V↔3,3 V dan GND bersama. Periksa skematik PCB, sinyal pin yang sudah terpakai, dan SOP sebelum wiring. |

**Risiko keselamatan:** perintah debug firmware `#pin_scan;` saat ini mencakup D19/RX1 dan D20/SDA, sehingga tidak boleh digunakan saat UART Pi atau bus I2C terhubung tanpa mitigasi/SOP. Skema dan pilihan akhir transport ditutup pada Tahap 7, **bukan keputusan final audit Tahap 0**.

## 4. Skenario QA dan kriteria penerimaan

1. Replay offline lima siklus AI_TEST valid menghasilkan **tepat satu** hasil inferensi dan tidak mengalirkan metadata ground truth ke masukan model.
2. ADC hilang, kanal tertukar, pesan rusak/duplikat, siklus tidak berurutan, nilai lingkungan tidak masuk akal, atau sequence berulang harus ditolak atau diberi status kualitas secara eksplisit.
3. Restart ATmega/Nextion di tengah akuisisi tidak boleh menampilkan hasil seolah-olah proses selesai; harus kembali ke status pemulihan yang sesuai.
4. Raspberry Pi mati, model tidak tersedia, atau inferensi melewati batas waktu → tampil **N/A**. Aktuator tetap mengikuti keadaan aman yang diatur ATmega. Berlaku setelah adapter komunikasi dan handler hasil benar-benar diterapkan.
5. Mode AMBIL DATA menyimpan CSV final secara aman hanya setelah validasi; file parsial dipertahankan di lokasi terpisah beserta alasan, bukan dihapus tanpa catatan.
6. Ukur p50/p95 latensi, penggunaan CPU/RAM, ukuran model, keandalan koneksi dan waktu pemulihan pada **Raspberry Pi 5 nyata**.
7. Setelah ada persetujuan terpisah, lakukan verifikasi tombol Nextion, fase pompa/valve, kegagalan SHT30, rekoneksi USB, serta pemulihan setelah listrik terputus.

## 5. Keputusan platform

- **Hybrid ATmega2560 + Raspberry Pi 5 — direkomendasikan.** ATmega tetap menjalankan akuisisi dan aktuator, sementara Pi menjalankan Python/sklearn, pipeline model, penyimpanan data, dan pencatatan hasil. Masih membutuhkan benchmark dan pembuktian pada perangkat.
- **Inferensi sepenuhnya di ATmega — dipertahankan sebagai opsi eksperimen.** SRAM ATmega hanya 8 KB; ukuran model, urutan fitur, pemetaan kelas dan kesesuaian MQ3 harus dibuktikan. Header model_rf.h historis tidak otomatis kompatibel dengan 62 fitur kandidat.
- **Kontrol seluruh perangkat dipindahkan ke Raspberry Pi — tidak direkomendasikan.** Cara ini menambah ketergantungan keselamatan aktuator pada sistem operasi dan komunikasi host.

## 6. Batas pekerjaan yang memerlukan persetujuan

Pengujian offline tidak boleh membuka COM5 saat dimiliki autosave listener, me-restart layanan yang aktif, mengunggah firmware/TFT, mengubah kalibrasi EEPROM, atau menggerakkan pompa/valve. Bukti kompilasi dan simulasi **bukan** pengganti pengujian fisik.
