# Diagnosis read-only firmware PCB kedua dan Nextion yang tertahan pada "Initializing Systems"

**Tanggal:** 13 November 2026, sekitar 17.48–17.58 WIB
**Branch:** `wahyu`
**Target:** PCB custom ATmega2560 kedua (bukan PCB COM5/SVM30), FT232RL onboard USB ke Raspberry Pi 5
**Ruang lingkup:** repository, status Pi, serial **pasif**, firmware/HMI, analisis akar masalah. **Tidak ada flashing, EEPROM write, kontrol aktuator, restart perangkat, atau RF500 live.**

## 1. Sumber awal, asumsi, dan identitas koneksi aktual

Laporan awal dibaca sebelum pemeriksaan:
`docs/reports/2026-11-12_SECOND_PCB_NEXTION_INITIALIZING_REMOTE_PREFLIGHT.md`
(dirujuk operator sebagai commit `b73b0c1c`). Laporan ini menyatakan
Nextion terhenti pada `Initializing Systems`, PCB kedua **tidak identik**
dengan perangkat SVM30 yang pernah diprogram dari COM5, dan identitas firmware
fisiknya **tidak diketahui**.

**Pemeriksaan langsung 13 November 2026:**

| Item | Observasi | Keputusan |
|---|---|---|
| SSH `enose-v3@enose-pi5` | Berhasil | **PASS** |
| Pi 5 daya | `vcgencmd get_throttled=0x0` | **PASS untuk flag undervoltage Pi saja**, bukan pemeriksaan rail PCB |
| USB FT232R | `lsusb` `0403:6001`, serial `A10KNJBL` | **PASS enumerasi FTDI**, bukan komunikasi MCU |
| Port | `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0` → `/dev/ttyUSB0` | **PASS** |
| Pemegang port | `fuser -v /dev/ttyUSB0` tidak menemukan pemilik | **PASS sebelum dan setelah pemeriksaan** |
| Layanan serial getty/ModemManager | Tidak aktif | **PASS** |
| Windows | `python -m serial.tools.list_ports -v` tidak menemukan COM pada laptop | **Sesuai koneksi USB yang sudah dipindah ke Pi** |
| Kernel USB | Disconnect lama pukul **17.03.47**, koneksi terbaru pukul **17.48.25**; **tidak ada disconnect baru saat capture** | **PASS selama capture**; insiden lama bukan bukti kestabilan jangka panjang |
| PCB idle / LCD | Dilaporkan operator idle dan tetap di `Initializing Systems`; tidak ada sensor kamera/layar live di SSH | **Pengamatan operator**, belum dapat diukur independen |

FTDI berada pada Pi saat diagnosis ini, bukan COM11 Windows. Penomoran COM11 adalah konfigurasi **saat USB berada di laptop**, tidak dipakai untuk uji ini.

## 2. Identifikasi firmware yang benar-benar terpasang

**Hasil: TIDAK TERIDENTIFIKASI.** Karena firmware fisik PCB kedua belum
pernah dibaca dari Flash, dan tidak ada penanda firmware yang berhasil
diamati dari UART, nama/versi image di repository **bukan bukti image
yang terpasang**.

Penanda yang seharusnya ada pada beberapa build source:

| Build source | Penanda / perilaku | Status fisik PCB kedua |
|---|---|---|
| Source default `src/main.cpp` | `SMART_COFFEE_BUILD_ID=take30-ai30-rfhost-20261110`; saat `setup()` mengirim `FW_HELLO` dan banner; `ENABLE_PI_RF30_RETURN` default 0 | **Tidak terbukti terpasang** |
| Kandidat `scripts/platformio_rf30_bench.ini` | Build ID sama; `ENABLE_PI_RF30_RETURN=1`, tanpa scan I²C seluruh alamat, dengan timeout Wire 25 ms | **Compile PASS, belum di-flash** |
| Source standalone SVM30 PCB lama | `SMART_COFFEE_BUILD_ID=standalone-svm30-bench-20261111`; model lokal tanpa Pi | **Milik PCB lain, bukan identitas PCB kedua** |
| Firmware fisik PCB kedua | Memerlukan `FW_HELLO`/log berpenanda atau readback chip | **Belum ada bukti** |

Perbandingan SHA256 artefak lokal:

```text
RF30 kandidat / build baru (Intel HEX):
26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6
Standalone SVM30 PCB lama (Intel HEX):
6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2
```

Image RF30 lokal **identik** dengan hasil `pio run -c
scripts/platformio_rf30_bench.ini -e rf30_return_bench`
(35.770 byte Flash aplikasi; 3.917 byte RAM global), dan dengan
file staging Pi. **Tidak ada checksum dari MCU PCB kedua** untuk
dibandingkan. Backup Flash/EEPROM SVM30/COM5 tidak dapat dipakai sebagai
rollback PCB baru.

## 3. Pembacaan UART pasif — bukti lapangan

Skrip: `scripts/pi_second_pcb_passive_id.py`
(QA: `scripts/test_pi_second_pcb_passive_id.py`).
Skrip Python di-copy ke staging user Pi lalu dijalankan **sekali** menggunakan
virtual environment pyserial 3.5. Identitas FT232R diverifikasi dari
symlink `by-id`. Sebelum membuka port, `serial.dtr=False`,
`serial.rts=False`, dan semua hardware/software flow control dimatikan.
**Glitch DTR yang terjadi pada implementasi driver saat open tetap
tidak dapat dikesampingkan.** Tidak ada `Serial.write` atau UART TX.
Durasi dibatasi **45 detik pada 115200 baud**, nilai dari
`src/main.cpp:268`, bukan ditebak.

Hasil:

```text
status                    SELESAI
baud                      115200
durasi_target_s           45
durasi_aktual_s           45.1
rx_bytes                  0
fw_hello_seen             false
build_ids_claimed         []
uart_tx_bytes             0
usb_disconnect_baru       false
usb_event_baru_count      0
pesan_error               null
mcu_flash_verified        false
```

Bukti byte asli **tanpa pemrosesan** disimpan:

- Pada Pi: `~/smart-coffee-stage7/rf30_staging/second_pcb_20261112_bootguard_v1/diagnostics_20261113_second_pcb_passive_01/`
- Salinan privat pada repo: `private/second_pcb_pi_readonly/diagnostics_20261113_second_pcb_passive_01/serial_pasif_mentah.bin`
- Metadata: `ringkasan.json` pada direktori yang sama
- SHA256 raw 0 byte (dicek lokal dan cocok dengan metadata):
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

Folder bukti ini **di-ignore Git** supaya UART raw tidak
dipublikasikan dan tidak mungkin membocorkan metadata perangkat.
Log tersebut benar-benar kosong: bukan output yang dibuang oleh parser.
Journal kernel terakhir tidak menunjukkan disconnect baru setelah
koneksi USB terbaru.

**Interpretasi terbatas:** log 0 byte tidak membuktikan MCU diam/mati
karena `FW_HELLO` dan `printWelcome()` pada source hanya dikirim
di awal `setup()`, sedangkan `adsCallback()` saat state `IDLE`
**tidak mencetak ADC JSON ke USB** (`src/main.cpp:1510–1550`).
Listener dibuka saat PCB sudah idle, **tanpa reset** atau
perintah handshake. Bahkan firmware yang sehat bisa tidak
mengirim apa pun selama 45 detik.
Kita sengaja tidak mengirim `#status;`: walaupun command itu ada
di source saat ini (`src/main.cpp:1408`), firmware fisik PCB kedua
belum diidentifikasi sehingga perilakunya tidak dapat dijamin.

## 4. Jalur startup ATmega → Nextion

Temuan dari `src/main.cpp` dan `src/nextion_transport.cpp`:

1. **`src/main.cpp:267–285`** — `setup()` mengawali
   `Serial.begin(115200)`, mengirim `FW_HELLO`,
   lalu `nextion.begin(9600)`, `bkcmd=0`, menyimpan `nextionBootMs`.
2. **`src/main.cpp:291–305`** — pada source default,
   `scanI2C()` memeriksa **alamat 1–126** memakai `Wire.endTransmission()`;
   kemudian `sensors.begin()` memanggil `ads*.begin()`
   dan SHT30 (lihat `src/sensor.cpp:57–101`).
3. **`src/main.cpp:307–333`** — kegagalan `sensors.begin()`
   yang mengembalikan `false` hanya menghasilkan **peringatan**
   dan **tidak sengaja memblokir scheduler**. Tetapi jika transaksi
   Wire tidak kembali/hang, eksekusi **tidak mencapai scheduler**.
4. **`src/main.cpp:1311–1317`** — `serialCallback()`
   harus dipanggil task scheduler sebelum mengevaluasi
   `millis() - nextionBootMs >= 3000` dan mengirim `pHome`.
   Angka tiga detik adalah **syarat waktu minimum sejak begin**, bukan
   jaminan boot selesai dalam tiga detik.
5. **`src/main.cpp:705–715`**, **`src/nextion_transport.cpp:27–38`** —
   kode menulis `page pHome` dengan terminator
   `FF FF FF` melalui **`Serial2` pada 9600 baud**.
6. **`src/main.cpp:1120–1133`** — handler
   `EVT:HMI_READY` dapat memicu restore halaman,
   **jika event benar-benar diterima**. String ASCII
   `EVT:HMI_READY` **tidak ditemukan** dalam file HMI
   acuan `RoastSense_NX4827T043_011_COMPILE_READY.HMI`,
   sehingga transisi timer dari MCU tidak dapat diasumsikan
   punya fallback dari event tersebut.

**Audit HMI offline:** `verify_nextion_atmega_contract.py`
PASS: model HMI, **12 halaman, 23 event**, handler source
dan jalur `Serial2/9600`. File HMI/TFT **yang terpasang di
Nextion fisik tidak dapat diverifikasi melalui USB FT232RL**.
HMI acuan yang lulus tes juga tidak membuktikan wiring
TX2/RX2, level tegangan, ground atau baud HMI fisik.

**Kandidat penting:** default `scanI2C()` tidak memiliki
timeout khusus dalam source ini. Jika bus SDA/SCL tersangkut
atau library sensor tidak kembali, task `serialCallback()`
tidak berjalan dan LCD dapat tetap menunjukkan splash.
Build RF30 kandidat (belum di-flash) meniadakan scan full
dan menambahkan `Wire.setWireTimeout(25000UL,true)`.
**Itu mitigasi yang masuk akal, bukan pembuktian
bahwa I²C memang bermasalah pada PCB kedua.**

## 5. Penentuan akar masalah dan keyakinan

**Akar masalah spesifik belum dapat dipastikan dari pembacaan pasif.**
Rantai masalah yang paling relevan secara logika adalah
**MCU tidak berhasil mengirim perintah `page pHome` melalui
UART2**, karena firmware tidak mencapai callback atau karena
jalur UART2/HMI fisik tidak menerima perintah. Tidak ada
pengukuran UART2/MCU reset/clock langsung, maka ini masih
hipotesis bercabang.

| Kandidat | Keyakinan | Bukti pendukung | Bukti yang diperlukan untuk menguji |
|---|---|---|---|
| Startup tertahan pada I²C sebelum scheduler `serialCallback` | **Sedang sebagai risiko source; rendah sebagai diagnosis fisik** | `scanI2C` / `sensors.begin` mendahului `scheduler.init`, tidak ada timeout default | Periksa SDA/SCL, kondisi boot, atau tracing MCU yang aman |
| Firmware PCB kedua berbeda dari source atau MCU tidak berjalan stabil | **Sedang sebagai kemungkinan** | Tidak ada readback/marker; bootloader COM11 pernah timeout di Windows | Baca signature, backup Flash/EEPROM PCB ini; cek clock/RESET/catu |
| Jalur `Serial2` ↔ Nextion putus/terbalik, baud/HMI TFT berbeda | **Sedang sebagai kemungkinan** | Kontrak source 9600 PASS, tapi wiring & TFT terpasang tidak pernah diverifikasi | Foto/skema dan ukur TX2/RX2/baud saat startup tanpa mengendalikan aktuator |
| FT232R/SERIAL0 rusak | **Rendah/tidak cukup bukti** | USB enumerate dan port pasif terbuka; RX idle kosong tidak diagnostik | Kontinuitas TXD0/RXD0 dan pemeriksaan reset/firmware fisik |
| RF500 di Pi menyebabkan splash tertahan | **Rendah** | Jalur `pHome` lokal ATmega/Nextion dan mendahului inferensi | Pulihkan boot MCU/HMI sebelum mengaktifkan bridge |

**Fakta dengan keyakinan tinggi** hanya mencakup enumerasi FT232R,
daya Pi tanpa flag throttling, 0 byte RX dalam 45 detik,
tidak ada disconnect baru, kontrak source HMI,
serta build firmware kandidat yang lolos secara offline.
Jangan menaikkan keyakinan penyebab fisik berdasarkan
ketiadaan data idle.

## 6. Kondisi RF500 dan batas keselamatan

Pemeriksaan **read-only** `pi_rf30_pi5_readiness.py`
sesudah USB kembali ke Pi menghasilkan:
`HOST_STAGED_NOT_MCU_VERIFIED`,
`rf_model_hash_verified=true`,
`staging_modules_missing=[]`,
`live_activation_allowed=false`.
Model RF500 pada Pi SHA256:
`b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
Firmware kandidat RF30 staged SHA256 sesuai build lokal.
Model masih perlu validasi lintas PCB dan prospektif,
dan label origin/confidence belum tersedia di pipeline
RF500 yang kini disiapkan.

**RF500 tetap DITAHAN.** Ini bukan kegagalan staging;
identitas/build MCU, startup Nextion, dan integrasi UART
fisik belum terverifikasi. Tidak ada layanan permanen Pi
yang diubah, tidak ada `joblib.load` selama preflight,
tidak ada bridge live dijalankan, dan tidak ada akuisisi.

## 7. Rencana perbaikan aman dan gerbang persetujuan manusia

1. **Perlu operator onsite; tanpa tindakan kontrol.**
   Konfirmasi situasi fisik saat ini dan sediakan foto
   kedua sisi PCB atau skematik jalur FT232RL ↔ ATmega,
   ATmega Serial2 ↔ Nextion, I²C ADS1115/SHT30,
   catu, RESET, dan clock. Ukur rail listrik/ground
   dengan alat yang sesuai. Jika tercium bau terbakar,
   komponen panas abnormal, atau suplai tidak stabil,
   **STOP** dan inspeksi kelistrikan sebelum pengujian.
2. **Perlu operator onsite dan persetujuan untuk pengukuran
   pada alat menyala.** Periksa SDA/SCL ketika startup
   dan UART2 (TXD2/RXD2) apakah terdapat frame `page pHome`
   pada 9600 baud. Jangan mengubah tegangan, menjalankan
   aktuator atau mengirim kontrol. Tanpa alat/logika probe,
   langkah ini belum dapat dieksekusi lewat SSH.
3. **Persetujuan khusus akses programmer/reset
   diperlukan sebelum mencoba bootloader atau ISP.**
   Pada PCB ini tidak ada tombol RESET; periksa dahulu
   jalur DTR# FT232RL → RESET ATmega atau gunakan ISP
   benar-benar tersambung. Baca **signature** ATmega2560
   `0x1e9801`; kemudian **backup asli Flash + EEPROM
   PCB kedua** secara read-only, simpan hash dan
   prosedur rollback terpisah. Jangan gunakan backup COM5.
4. **Persetujuan flashing terpisah diperlukan.** Setelah
   backup lengkap dan skema terverifikasi, evaluasi kandidat
   RF30 bounded-I²C, tulis hanya aplikasi MCU dan verify.
   Jangan menulis EEPROM, fuse atau TFT tanpa SOP terpisah.
   Uji startup sampai `pHome` sebelum uji sensor aktif.
5. **Persetujuan uji fisik operator diperlukan.** Setelah
   MCU/HMI sehat, verifikasi 30 siklus/900 sampel,
   protokol balasan RF, `AI_RESULT_ACK`, kualitas prediksi
   lintas PCB dan fitur yang belum lengkap; baru
   pertimbangkan aktivasi RF500 live.

**Stop condition tercapai pada batas langkah berikutnya:**
pemeriksaan/aksi fisik RESET/ISP, pengukuran board menyala,
atau flashing membutuhkan operator dan persetujuan manusia.
Pengujian read-only yang dapat dilakukan dari SSH telah selesai.

## 8. Pengujian dan integritas pekerjaan

| Pengujian | Hasil |
|---|---|
| `python scripts/test_pi_second_pcb_passive_id.py` | PASS |
| `python -m compileall -q` listener & tes | PASS |
| `python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py` | PASS |
| `python scripts/test_rf30_boot_guard.py` | PASS source contract |
| `pio run -c scripts/platformio_rf30_bench.ini -e rf30_return_bench` | PASS compile-only |
| `python scripts/test_pi_rf30_pi5_readiness.py` | PASS fail-closed test |
| Pi live: by-id USB, power, serial passive 45s | PASS koneksi; RX 0 byte, firmware UNKNOWN |
| EEPROM/Flash readback & write | NOT RUN (belum diizinkan/terverifikasi) |
| Nextion fisik, 30 siklus, RF500 live | BLOCKED |

Tidak ada IP Tailscale, token, kredensial, atau UART raw yang
dimasukkan ke Git. Perubahan pengguna pada CSV/HMI dan
konfigurasi lokal tetap dipertahankan. Bukti privat
diterbitkan **hanya dalam workspace lokal/Pi**, bukan GitHub.
