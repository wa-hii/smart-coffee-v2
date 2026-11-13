# Nextion masih "Initializing Systems" walaupun daya Pi sudah pulih

**Tanggal:** 13 November 2026 WIB.
**Branch:** `wahyu`.
**Target:** PCB ATmega2560 kedua, Nextion 4,3 inci, FT232RL onboard di Raspberry Pi 5.

## Bukti terbaru

Operator mengonfirmasi bahwa layar fisik **masih** menampilkan
`Initializing Systems` setelah suplai custom 5 V diperbaiki dan
Raspberry Pi berhasil boot tanpa flag undervoltage
(`get_throttled=0x0`). Ini adalah **observasi operator**; belum
ada pengukuran langsung atas daya, TX/RX atau versi firmware Nextion
fisik.

Pada pemeriksaan read-only, FT232R `A10KNJBL` masih tersedia
di `/dev/ttyUSB0`. Firmware ATmega fisik belum teridentifikasi,
dan probe UART0 pasif 115200 baud dalam kondisi idle sebelumnya
menerima **0 byte**, yang tidak membuktikan MCU mati:
source `adsCallback()` tidak menyiarkan data sensor ketika idle.

## Verifikasi source dan HMI tanpa hardware

- `src/main.cpp:267–284`: `Serial.begin(115200)` dan `nextion.begin(9600)`.
- `src/main.cpp:291–305`: build default
  (`ENABLE_PI_RF30_RETURN=0`) menjalankan scan I²C penuh,
  baru kemudian `sensors.begin()`. Build RF30 candidate
  menambahkan I²C timeout dan meniadakan scan otomatis,
  **tetapi belum terpasang pada board fisik yang diketahui**.
- `src/main.cpp:326–332`: task Serial diaktifkan
  **setelah** semua inisialisasi sensor dan kalibrasi.
- `src/main.cpp:1311–1317`: callback task Serial mengirim
  `showNextionPage("pHome")` setelah timer minimum 3 detik.
  Jangka tiga detik **tidak** berarti tiga detik sejak
  perangkat diberi daya jika inisialisasi sebelumnya tertahan.
- `src/main.cpp:705–716` dan
  `src/nextion_transport.cpp:13–36`: `page pHome`
  dikirim pada Serial2 9600 8N1, diakhiri
  tiga byte `FF FF FF`.
- Proyek referensi `RoastSense_NX4827T043_011_COMPILE_READY.HMI`
  memiliki `pSplash` (846 byte blob) dan `pHome`
  (4184 byte blob). Pengecekan offline pada `pSplash`
  **tidak** menemukan instruksi literal `page pHome`
  atau event `EVT:HMI_READY`; transisi bergantung pada
  perintah MCU dalam source ini. HMI/TFT **terpasang**
  belum terbukti sama dengan referensi repo.
- `python scripts/test_rf30_boot_guard.py`: PASS source contract.

## Pohon diagnosis yang dapat memisahkan akar masalah

Selanjutnya perlu **persetujuan operator untuk pemeriksaan
fisik alat dalam kondisi menyala**. Jangan memulai pompa,
valve, akuisisi, flashing, pemrograman EEPROM, atau
memasang kabel tambahan tanpa skematik/pinout.

1. **Konfirmasi koneksi listrik saat perangkat dimatikan:**
   dokumentasikan skematik/foto area konektor Nextion,
   MCU, serta label UART2. Pastikan sistem aman dan
   ground/suplai sesuai spesifikasi masing-masing.
2. **Jika operator memiliki logic analyzer/oscilloscope
   yang sesuai dan menyetujui pengukuran live:**
   amati TXD2 ATmega menuju RX Nextion **tanpa mengirim
   stimulus** saat startup yang diawasi. Sinyal target
   9600 baud, 8N1; pesan yang dicari pada source saat
   selesai inisialisasi ialah `page pHome` diikuti
   `FF FF FF`. MCU PH1/TXD2 adalah TQFP-100
   physical pin 13, **bukan** header D13; jika
   tersedia header Arduino Mega setara D16 (TX2).
   Pin fisik PCB custom wajib dipastikan lewat skematik.
3. **Jika paket terlihat di TXD2 MCU tetapi tidak
   terlihat di jalur RX Nextion**, kemungkinan kabel,
   konektor, ground atau antarmuka level; lakukan
   perbaikan wiring hanya setelah verifikasi rangkaian.
4. **Jika paket sampai ke RX Nextion tetapi LCD
   tetap pada splash**, periksa file TFT yang benar-benar
   terpasang, baud fisik Nextion, nama `pHome`,
   dan daya LCD; jangan langsung mengganti TFT.
5. **Jika tidak ada paket dari TXD2**, masalah ada
   sebelum atau pada komunikasi MCU: versi firmware
   belum cocok dengan source, MCU tidak menjalankan
   `setup()`/scheduler, I²C/SDA/SCL tertahan,
   RESET, clock atau catu MCU. Tahap berikut adalah
   identifikasi chip dan backup Flash+EEPROM fisik
   dengan jalur programmer yang benar, dengan
   persetujuan terpisah.

**Keterbatasan:** tidak ada instrumen di sisi software
yang dapat membaca pin TXD2, RESET, SDA/SCL secara
fisik melalui FT232RL yang saat ini hanya terhubung
ke Serial0. `get_throttled=0x0` hanya mengonfirmasi
status daya Raspberry Pi, bukan MCU dan Nextion.
Data UART0 idle juga tidak dapat membuktikan bahwa
perintah UART2 `page pHome` telah dikirim.

## Keputusan

- Status Pi + FT232R: PASS pada pemeriksaan terbaru.
- Status display: **GAGAL BERPINDAH KE pHome menurut operator**.
- Penyebab fisik spesifik: **BELUM DIKETAHUI**;
  risiko scan/akses I²C sebelum scheduler penting
  tetapi **bukan diagnosis pasti**.
- RF500: tetap **DITAHAN**.
- Flash, EEPROM, serial TX, aktuator: **TIDAK DIJALANKAN**.

**Bukti paling penting berikutnya adalah rekaman
TXD2/RX Nextion pada startup**, atau foto kedua
sisi PCB yang memungkinkan menentukan net dan
titik ukur yang aman.
