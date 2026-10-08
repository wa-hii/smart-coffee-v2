# Panduan Nextion Editor — RoastSense NX4827T043_011

**Layar target:** NX4827T043_011 (Basic), resolusi **480 × 272 piksel** dengan komunikasi UART **9600 baud, 8N1**. Pengendali antarmuka pada integrasi yang sudah ada adalah **ATmega2560**.

Sumber visual utama adalah desain Figma final pada **UI-ENOSE**. Dua belas frame hasil ekspor di folder backgrounds_clean_png/ dan mockups_png/ harus dipertahankan identik. Jangan menggambar ulang, mengganti warna, mengubah ukuran atau mengganti desain yang telah dikunci.

## 1. Proyek HMI yang menjadi acuan

Gunakan proyek:

    project/RoastSense_NX4827T043_011_COMPILE_READY.HMI

Perbaikan Figma pada halaman **00_Splash** sudah dimasukkan ke proyek HMI ini. Halaman **01_Home sampai 11_Alert** tidak dibuat ulang, sehingga penyempurnaan ukuran teks dan tata letak yang telah disimpan manual lewat Nextion Editor tetap dipertahankan.

Karena proyek HMI canonical sudah pernah disimpan melalui Nextion Editor, susunan biner internalnya mengikuti editor dan dapat berbeda dari hasil generator awal. Untuk revisi tampilan, ubah hanya sumber gambar yang diperlukan. **Validasi struktur terakhir wajib menggunakan fitur Compile pada Nextion Editor.**

Jangan memakai file lama **RoastSense_NX4827T043_011.HMI** atau **RoastSense_NX4827T043_011_FIXED.HMI** untuk membuat TFT final. Versi COMPILE_READY telah membuang empat objek pSplash lama dan menonaktifkan empat perintah inisialisasi lama yang sebelumnya memunculkan kesalahan Invalid Variables.

TFT lama pada folder build/ dibuat sebelum sinkronisasi akhir dengan Figma dan **belum dapat dianggap sebagai hasil final**. Buka HMI canonical, lakukan kompilasi menggunakan Nextion Editor, periksa simulator, lalu unggah TFT terbaru ke layar **setelah ada persetujuan pengujian fisik**.

## 2. Pembuatan HMI yang dapat direproduksi

Perintah generator lama berikut hanya merupakan referensi untuk menyiapkan ulang aset berdasarkan baseline lama. **Jangan menjalankannya langsung pada HMI canonical final karena berisiko menimpa hasil edit manual.** Gunakan output terpisah bila perlu eksperimen:

    python nextion/NX4827T043_011/tools/build_figma_fix_hmi.py --baseline nextion/NX4827T043_011/project/RoastSense_NX4827T043_011.HMI --images nextion/NX4827T043_011/backgrounds_clean_png --output nextion/NX4827T043_011/project/RoastSense_NX4827T043_011.HMI

Generator melakukan verifikasi CRC model layar, CRC 12 halaman, checksum direktori, komponen dinamis yang wajib ada, dan event sentuhan. Untuk memeriksa kontrak HMI–ATmega secara offline:

    python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py

Pemeriksaan ini juga memastikan aset HMI sesuai gambar Figma yang terkunci serta seluruh event HMI diwakili dalam firmware ATmega. **PASS offline tidak menggantikan kompilasi editor atau pengujian layar fisik.**

## 3. Urutan 12 halaman Nextion

| No. | Halaman Nextion | Layar rancangan |
|---|---|---|
| 1 | pSplash | 00_Splash |
| 2 | pHome | 01_Home |
| 3 | pTake | 02_TakeData |
| 4 | pDataRun | 03_DataRun |
| 5 | pDataDone | 04_DataDone |
| 6 | pTest | 05_StartTest |
| 7 | pTestRun | 06_TestRun |
| 8 | pResult | 07_TestResult |
| 9 | pCal | 08_Calibration |
| 10 | pSettings | 09_Settings |
| 11 | pHistory | 10_History |
| 12 | pAlert | 11_Alert |

Berkas **component_map.csv** menjadi acuan posisi serta ukuran komponen/hotspot dinamis. Folder **nextion_events/** berisi instruksi event **Touch Release** yang sesuai.

## 4. Protokol komunikasi Nextion dan ATmega

Event sentuhan dari Nextion dikirim sebagai baris ASCII:

    prints "EVT:DATA_START",0
    printh 0D 0A

Parser ATmega hanya menerima karakter ASCII yang dapat dicetak ditambah CR/LF. Paket respons biner bawaan Nextion ditolak. Firmware mengirim **bkcmd=0** saat awal menyala agar respons command tidak bercampur dengan event.

Perintah dari ATmega menuju Nextion menggunakan terminator standar **FF FF FF**.

### Koneksi kabel

- **Nextion TX → ATmega2560 PH0/RXD2**, pin fisik IC **8**.
- **Nextion RX ← ATmega2560 PH1/TXD2**, pin fisik IC **9**.
- **GND → GND**.

Pada header board Arduino Mega 2560, kedua sinyal tersebut adalah **RX2/D17 dan TX2/D16**. Firmware produksi menggunakan **Serial2**. **Pin fisik IC 8/9 bukan pin digital Arduino D8/D9.**

## 5. Alur AMBIL DATA

    pHome → pTake → pDataRun → pDataDone

- ATmega memegang state machine dan menjalankan seluruh alur.
- Tombol tingkat roasting memilih **LIGHT, MEDIUM, DARK**.
- Tombol origin memilih kode asal kopi yang tersedia.
- Batch dapat dinaikkan atau diturunkan, minimum **B01**.
- Jumlah siklus berasal dari konfigurasi **ACQ_REPETITIONS** pada src/main.cpp.
- Nama CSV otomatis mengikuti pola **roast-origin_Bxx.csv**.
- START hanya dapat diaktifkan ketika pilihan sah dan sensor yang disyaratkan siap.
- Tombol PAUSE melakukan jeda serta melanjutkan kembali fase/timer yang sedang berlangsung.
- Listener host secara pasif menyimpan labeled_data; event perubahan fase tidak boleh dianggap sebagai baris sensor.

## 6. Alur START TEST dan AI

    pHome → pTest → pTestRun → pResult

Implementasi yang **sudah ada** menggunakan ATmega saja: START AI TEST mengaktifkan state machine akuisisi yang sama pada mode AI_TEST, kemudian ATmega memanggil modul Inference yang tersedia.

Jika **USE_ON_DEVICE_INFERENCE** dinonaktifkan atau tidak ada model yang memberi hasil terverifikasi, layar menampilkan **N/A**. Origin, confidence, dan probabilitas juga N/A selama belum ada sumber hasil AI yang sah. **Hasil dari Raspberry Pi 5 tidak boleh ditampilkan seolah-olah sudah tersedia**, karena jalur tersebut masih dalam perencanaan.

## 7. Kalibrasi, pengaturan, riwayat, dan notifikasi

- **CALIBRATION** hanya dijalankan saat akuisisi berhenti. Fungsi SensorArray::calibrate() menghitung R0 dan menyimpannya ke EEPROM, lalu sistem membaca ulang. Aktivasi pada hardware membutuhkan persetujuan.
- **RESET** mengembalikan pilihan antarmuka dan kecerahan layar, **bukan** menghapus kalibrasi sensor.
- **HISTORY** menyimpan empat ringkasan antarmuka terbaru dalam RAM ATmega.
- Tombol final bertuliskan **EXPORT** masih mengirim token lama EVT:HISTORY_CLEAR; firmware menerjemahkannya sebagai **ekspor ke Serial USB**, bukan menghapus data.
- **RESULT SAVE** mengirim hasil inferensi lokal yang tersedia ke Serial USB.
- **EXIT** menghentikan akuisisi/aktuator, menampilkan keadaan aman, dan meminta pemadaman daya secara manual.

## 8. Checklist QA sebelum flashing

Jalankan perintah berikut tanpa mengunggah firmware:

    pio run -e mega2560
    pio run -e nextion_test
    python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py

Sesudah itu, **dengan persetujuan pengujian hardware**, buka HMI canonical di Nextion Editor, lakukan Compile, uji tiap halaman di simulator, lalu unggah hasil TFT terbaru ke perangkat dan verifikasi komunikasi serial dua arah.

Jangan menyamakan **verifikasi offline**, **kompilasi editor**, **simulasi editor**, **upload TFT**, dan **pengujian perangkat nyata** sebagai bukti yang identik.
