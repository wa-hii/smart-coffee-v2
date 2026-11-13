# Audit menyeluruh E-Nose PCB kedua: FT232RL onboard, COM11, ATmega2560, Nextion dan RF500

**Tanggal audit:** 13 November 2026 (WIB)
**Target:** PCB custom **kedua** dengan ATmega2560 dan, berdasarkan konfirmasi operator, **IC FT232RL terpasang pada PCB**. Bukan perangkat lama yang menggunakan COM5 untuk SVM30.
**Pelaksanaan:** pemeriksaan Windows, repo sumber, kompilasi firmware, tes offline, dan Tailscale (tidak membuka serial atau melakukan flash pada audit ini).

## 1. Koreksi arsitektur hardware

Konfirmasi fisik operator bahwa IC FT232RL terdapat **di PCB** mengoreksi interpretasi sebelumnya yang menyebutnya sebagai modul/adaptor USB–TTL eksternal. Jalur yang dimaksud adalah:

```text
Laptop Windows USB / COM11
  -> USB PCB -> FT232RL onboard (USB–UART, 0403:6001)
  -> [TXD/RXD/VCCIO/GND, dan DTR bila dirancang] -> ATmega2560 Serial0 115200
       | -> Serial2 9600 -> Nextion 4,3 inci
       | -> I2C SDA20/SCL21 -> 4 ADS1115 + SHT30
       | -> keluaran pengendali aktuator PCB

Target runtime: USB PCB dipindah dari laptop ke Raspberry Pi 5, lalu
Pi menjalankan RF500 dan mengembalikan hasil prediksi ke UART ATmega.
```

FT232RL **bukan** programmer ISP internal dan bukan ATmega2560. Enumerasi COM11 hanya membuktikan antarmuka USB–UART merespons. Bootloader ATmega yang cocok dan jalur reset DTR **belum dapat dipastikan**.

Referensi hardware resmi:
- FTDI FT232RL: https://ftdichip.com/products/ft232rl/
- FTDI FT232R datasheet: https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf
- Arduino Mega2560 automatic reset: https://store.arduino.cc/products/arduino-mega-2560-rev3

Pada FT232RL paket SSOP-28, **pin 1 TXD**, **pin 5 RXD**, **pin 2 DTR#**, **pin 4 VCCIO**, dan **pin 19 RESET# milik FT232RL sendiri**. Untuk auto-reset MCU, rancangan seperti Arduino Mega memakai DTR melalui **kapasitor sekitar 100 nF** ke net RESET MCU, dengan penarikan RESET sesuai rancangan. **Jangan hubungkan langsung pin FTDI RESET# (pin 19) sebagai pengganti DTR#**. Pinout tersebut adalah referensi chip, **bukan bukti net PCB ini**; wajib verifikasi skematik/continuity sebelum modifikasi.

## 2. Hasil audit bukti hardware dan host

| Area | Hasil terukur | Keputusan |
|---|---|---|
| Windows USB/driver | `COM11`, USB Serial Port, `VID:PID 0403:6001`, serial `A10KNJBLA`; Windows PnP `OK` | **PASS enumerasi FT232R-family**, bukan MCU |
| Receiver port | Proses auto-receiver PID 15160 dihentikan sesi sebelumnya; pemeriksaan terbaru tidak menemukan receiver/AVRDUDE aktif. Folder `data/raw/.incoming` kosong | **PASS port tidak diperebutkan**, status file receiver dapat stale |
| Komunikasi bootloader | Upaya `avrdude 6.3 -p m2560 -c wiring -P COM11 -b 115200 -n -v` pada 13 November menghasilkan `stk500v2_ReceiveMessage(): timeout` | **FAIL/TIDAK TERKONFIRMASI**, tanpa signature |
| Riwayat akses melalui Pi | FT232R `A10KNJBL` pernah muncul di `/dev/ttyUSB0`, passive RX 8 detik = **0 byte**, bootloader probe `wiring` = timeout | Endpoint USB pernah terbaca; tidak membuktikan MCU |
| Backup PCB kedua | Tidak ada backup Flash dan EEPROM yang dapat diverifikasi pada lokasi privat lokal/Pi yang terakhir berhasil diperiksa | **BLOCKED untuk flashing** |
| Firmware aktif chip | Belum dibaca atau diidentifikasi | **UNKNOWN**; firmware SVM30 COM5 berasal dari **PCB lain** |
| Catu/RESET/clock/PCB wiring | Belum ada skematik, foto kedua sisi, probe RESET, continuity TX/RX, pengukuran 5V/AVCC/VCCIO, atau clock 16MHz dari board kedua | **BELUM DIVERIFIKASI** |
| Layar fisik | Operator terakhir melaporkan `Initializing Systems`; tidak ada observasi HMI fisik terbaru | **BELUM LULUS startup** |
| Raspberry Pi via Tailscale | Laptop Tailscale berjalan; `enose-pi5` berstatus **offline, last seen sekitar 1 jam** pada pemeriksaan; `tailscale ping`, ping IP `100.103.211.125`, dan SSH timeout | **BLOCKED runtime Pi saat ini** |

Perlu membedakan status ini: FT232RL yang muncul sebagai COM11 **tidak membuktikan** VCC/AVCC ATmega sehat, RESET high, clock berjalan, bootloader terisi, atau firmware memulai scheduler. Pemindahan USB dari Pi ke laptop tidak memperbaiki timeout bootloader.

## 3. Audit firmware dan Nextion

| Aspek | Bukti dari source/QA | Status |
|---|---|---|
| UART komputer | `Serial.begin(115200)`; komunikasi port USB FT232RL, jika net UART0 benar | **PASS source, belum hardware** |
| UART LCD | `Serial2.begin(9600)` via `NextionTransport` | **PASS source, belum hardware** |
| HMI | Verifikator proyek: **12 halaman, 23 event**, semua event ada di handler, model HMI dan tipe widget cocok | **PASS offline** |
| Peralihan pSplash | `serialCallback()` memanggil `pHome` setelah kira-kira **3 s**, atau saat `EVT:HMI_READY`; callback baru aktif setelah `sensors.begin()` dan `scheduler.init()` | **Hipotesis startup terhambat sebelum scheduler**, belum bukti |
| Init sensor | Empat ADS1115 alamat `0x48–0x4B`, SHT30 I2C; sensor dapat gagal namun source tetap mencoba scheduler | **Belum dibuktikan fisik** |
| Hardening kandidat RF30 | Hindari scan I2C semua alamat saat boot dan pasang timeout `Wire.setWireTimeout(25000UL,true)` | **PASS source/compile, belum ter-flash** |
| Kompilasi RF30 | `pio run -c scripts/platformio_rf30_bench.ini -e rf30_return_bench`: **SUCCESS**, Flash **35.770 B**, global RAM **3.917 B** | **PASS** |
| Image kandidat | SHA256 build `.pio/build/rf30_return_bench/firmware.hex` == kandidat privat **26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6** | **PASS byte-for-byte** |
| Batas aplikasi | Intel HEX hanya mengisi 35.770 byte awal, tidak mengalamatkan bootloader region | **PASS format**, bukan verifikasi perangkat |
| Upload RF30 | Belum ada signature dan backup PCB kedua; **tidak dilakukan** | **BLOCKED** |

Ada **risiko konfigurasi salah port**: `platformio.ini` lokal masih menyebut `upload_port=COM4` dan `monitor_port=COM4` (file ini memiliki perubahan lokal yang tidak boleh ditimpa). Jangan menjalankan upload default tanpa override/identifikasi target; gunakan profil build terisolasi dan target eksplisit hanya setelah programmer benar-benar berkomunikasi.

Gejala Nextion `Initializing Systems` dapat disebabkan oleh MCU tidak mencapai loop, hang I2C, UART2/tata sambung salah, baud/HMI tidak sesuai, atau daya. **Tidak cukup bukti untuk memilih salah satunya.** Boot guard kandidat tidak otomatis menyembuhkan firmware lama yang belum diketahui.

## 4. Akuisisi data dan RF500

- Take Data dan AI Test dalam source masing-masing memakai **30 siklus** × (25 s purging + 5 s collecting) = **900 detik** / **900 sampel pada 1 Hz**.
- QA software lulus untuk parsing, urutan fase, 900 sampel, penolakan input 5 siklus, frame hilang dan label bocor dari test.
- RF500 pada Pi telah dipersiapkan sebelumnya, SHA256 model `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`. Pada pemeriksaan 12 November Pi pernah menjalankan replay memakai model asli, **bukan** uji E2E fisik.
- Tiga fitur: `tgs822_max_mean`, `tgs822_purging_mean_mean`, `mq8_max_mean`, memakai **ADC absolut**. Pergantian PCB dapat menggeser distribusi ADC; kalibrasi/validasi lintas perangkat belum lulus.
- Balasan protokol RF30: `#rf30:<token>:<light|medium|dark>;`; firmware memvalidasi sesi, menampilkan roast di `pResult`, lalu `AI_RESULT_ACK`. Belum ada ACK fisik.
- **Origin belum diklasifikasi**; `tOrigin`, `tRConf`, `tOConf` secara eksplisit ditulis `N/A`, tiga progress probability diisi 0. Karena itu sistem RF500 **hanya menyediakan roast label**, belum origin/probability; tidak boleh mengklaim fitur tersebut sudah siap.
- Pi 5 **saat audit ini offline di Tailscale**, sehingga status service/model live tidak dapat diverifikasi atau diaktifkan. Koneksi USB yang sekarang berada di laptop juga memang tidak tersedia pada Pi.

## 5. Prioritas pemulihan dan bukti kelulusan

1. **P0: diagnosis board ATmega sebelum flash.** Dengan alat tak beroperasi dan catu terkendali, periksa VCC/AVCC/GND ATmega, VCCIO FT232RL, jalur FT232RL pin 1 TXD → ATmega RXD0, FT232RL pin 5 RXD ← ATmega TXD0, FT232RL pin 2 DTR# → rangkaian kapasitor auto-reset → net RESET MCU, level RESET, clock, dan kemungkinan konflik suplai USB–PSU. Periksa dengan skematik/continuity dan pengukur yang sesuai; hindari mengasumsikan pin header fisik sama dengan Mega R3.
2. **P0: buktikan akses pemrograman.** Tanpa tombol RESET, jika DTR auto-reset dan bootloader ada, port COM11 dapat dipakai. Jika tidak, gunakan ISP melalui jalur MISO/MOSI/SCK/RESET/VCC/GND dengan programmer yang kompatibel. Uji baca signature ATmega2560 yang semestinya `0x1e9801` sebelum tindakan tulis. Tidak perlu memasang FT232RL eksternal.
3. **P0: backup asli PCB kedua.** Baca Flash dan EEPROM, rekam signature, hash, area aplikasi dan rollback, termasuk evaluasi perlindungan baca. Backup SVM30/COM5 lama **tidak berlaku** untuk alat ini.
4. **P1: deployment satu kali** kandidat RF30 setelah seluruh gerbang lulus, tanpa mengubah EEPROM/HMI, dengan verifikasi readback dan tes startup Nextion `pHome`.
5. **P1: pulihkan Pi/Tailscale** dan kembalikan sambungan USB PCB ke Pi *setelah* flash selesai. Bukti kelulusan: SSH, by-id USB FT232R, `FW_HELLO`, ACK end-to-end, 30 siklus/900 sampel utuh, prediksi roast tampil di Nextion.
6. **P2: kualitas AI** uji lintas PCB dan kopi referensi Light/Medium/Dark; latih origin model dan probabilitas terkalibrasi secara terpisah bila kedua fitur diperlukan.

## 6. Keputusan audit

**Hasil:** Software kandidat RF30 + kontrak HMI + integrasi RF500 offline **PASS**. Komunikasi USB–FT232RL **PASS enumerasi**. Komunikasi bootloader/ATmega **BELUM PASS**, backup PCB kedua **TIDAK TERVERIFIKASI**, Nextion fisik masih memiliki gejala startup (laporan terakhir), dan Raspberry Pi **OFFLINE saat pengujian**. **Tidak ada upload firmware yang bisa dinyatakan final.**

Audit ini **tidak membuka COM11**, tidak mengubah jalur DTR, tidak menggerakkan aktuator, tidak menghapus EEPROM, tidak menulis firmware dan tidak mengubah firmware Nextion.
