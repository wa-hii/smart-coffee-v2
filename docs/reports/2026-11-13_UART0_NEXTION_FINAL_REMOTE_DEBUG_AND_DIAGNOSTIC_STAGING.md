# UART0 FT232R dan UART2 Nextion: diagnosis langsung, build diagnostik, dan gerbang final

**Tanggal:** 13 November 2026 sekitar 19.01–19.17 WIB

**Branch:** `wahyu`
**Perangkat:** PCB ATmega2560 **kedua**, FT232R onboard terhubung melalui USB ke Raspberry Pi 5, bukan COM11 Windows.

## 1. Keselamatan dan kondisi awal

Operator memastikan wiring PCB–Nextion telah diperiksa dan sesuai.
Pengukuran host Pi `vcgencmd get_throttled=0x0`,
`pmic_read_adc EXT5V_V` sekitar **5,10–5,12 V**.
FT232R USB `A10KNJBL` terdeteksi pada
`/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0`
→ `/dev/ttyUSB0`; tidak ada proses pemegang port.

Yang **BELUM** diukur secara langsung dari Pi:
rail VCC/AVCC ATmega, RESET, XTAL, SDA/SCL
dan jalur UART2 menuju Nextion. Pernyataan operator
bahwa wiring benar dicatat; belum ada hasil pembacaan
fisik pada titik-titik tersebut dalam sesi ini.

## 2. Uji komunikasi UART0 non-kontrol

Source `src/main.cpp:1389–1411` menerima
`#status;` yang hanya memanggil `printWelcome()`,
tanpa memulai akuisisi atau mengendalikan aktuator.
Skrip baru `scripts/pi_second_pcb_status_handshake.py`
memverifikasi FT232R by-id, `get_throttled=0x0`,
serta tidak ada pemegang port. Skrip mengatur
`dtr=False`/`rts=False` **sebelum port dibuka**
dan mengirim tepat satu `#status;` pada **115200 baud**.
Port ditutup setelah sekitar **12 detik**.
Driver masih mungkin menimbulkan pulsa DTR sesaat
ketika membuka port; tidak dapat dikesampingkan
tanpa pengukuran fisik.

**Hasil pada Pi:**

```text
status= DONE
uart_tx_bytes= 8
command_transmitted_count= 1
uart_rx_bytes= 0
response_welcome_seen= false
response_info_seen= false
kernel_new_usb_events= []
post_throttle= throttled=0x0
eeprom_written= false
mcu_programmed= false
actuator_commands_sent= false
```

Sistem operasi/driver menerima 8 byte untuk
transmisi, **bukan** bukti TX secara listrik telah
diterima oleh RX0 ATmega. Tidak ada balasan
terlihat dari MCU. Jika firmware fisik benar-benar
sesuai source dan telah mencapai `serialCallback()`,
hasil ini tidak sesuai dengan kontrak `#status;`.
Namun karena versi firmware fisik belum diketahui,
**tidak boleh** menyimpulkan MCU/FT232R rusak.

Log byte mentah (panjang **0 byte**) dan manifest
berada di direktori **privat yang di-ignore Git**:
`private/second_pcb_pi_readonly/diagnostics_20261113_status_handshake_01/`.
SHA256 log kosong:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## 3. Identifikasi bootloader pascaperbaikan daya

Satu percobaan **AVRDUDE read-only, no write** dari Pi
melalui FT232R yang sama:

```text
avrdude 7.1 -p m2560 -c wiring -P <by-id-FT232R> -b 115200 -n -v
avrdude stk500v2_recv() error: timeout
process exit: 124 (bounded timeout 18 detik)
```

Paket AVRDUDE pada Pi memerlukan
`LD_LIBRARY_PATH` ke direktori library
toolchain yang sudah di-staging; percobaan
pertama gagal di loader sebelum port dibuka,
lalu satu percobaan sebenarnya berjalan dengan
library ditemukan dan berakhir timeout.

**Tidak ada signature `0x1e9801`, tidak ada
backup Flash/EEPROM yang berhasil dibaca,
tidak ada firmware yang di-flash**.
UART FT232RL onboard **bukan programmer ISP**
tanpa jalur SPI/RESET yang dibutuhkan.
Tidak dilakukan pengulangan probing tanpa batas.

## 4. Isolasi masalah source untuk Nextion

Source produksi saat ini:

- UART0 (`Serial`) **115200** melalui FT232R.
- UART2 (`Serial2`) **9600** menuju Nextion.
- `scanI2C()` atau `sensors.begin()` pada
  build default berjalan sebelum `scheduler.init()`
  dan `taskSerial.enable()`.
- `page pHome` baru dikirim task serial
  minimal 3 detik setelah begin Nextion,
  **bila startup MCU mencapai scheduler**.
- Build RF30 candidate yang lama sudah
  memiliki pengaman timeout I²C, tetapi
  firmware fisik MCU belum bisa dicocokkan.

Untuk memisahkan `I2C startup hang` dari
`UART/Nextion gagal` dibuat firmware
**isolasi UART0 + UART2 secara terpisah dan
HANYA compile-only**:

- `diagnostics/uart_nextion/src/main.cpp`
- `scripts/platformio_uart_nextion_diag.ini`
- `scripts/test_uart_nextion_diag_source.py`

Fitur firmware isolasi:

1. Tidak menginisialisasi I²C, ADS1115, SHT30,
   EEPROM, RF500, sensor, pompa atau akuisisi.
2. Menjaga D10 dan D11 LOW (asumsi pin valve-off
   mengikuti source; **perlu verifikasi PCB kedua
   sebelum firmware ini dipasang**).
3. UART0 115200 mengirim `UART_DIAG BOOT`,
   heartbeat setiap 5 detik dan jawaban
   khusus `#status;`/`#help;`. Semua
   perintah kontrol lain ditolak.
4. UART2 9600 mengirim `page pHome`
   + terminator `FF FF FF`, dengan
   tiga percobaan terbatas.
5. Mengirim `sendme` untuk meminta
   balasan LCD `0x66 <page_id> FF FF FF`;
   hanya menganggap home berhasil bila
   ID halaman **1** benar-benar diterima.
   Seluruh balasan dipantulkan sebagai
   JSON `UART_DIAG NEXTION_PAGE_REPLY`
   ke UART0. Ini memisahkan perintah
   dikirim dari balasan LCD benar-benar diterima.

**Hasil kompilasi offline:**

```text
pio run -c scripts/platformio_uart_nextion_diag.ini -e uart_nextion_diag
SUCCESS
Flash 4.750 byte
RAM global 426 byte
SHA256 firmware.hex:
87be0d01364f170190204be05e8310a2b920dea077d34380520c0ce75254c936
```

Image hasil build disalin **hanya** ke staging:
`~/smart-coffee-stage7/rf30_staging/second_pcb_20261112_bootguard_v1/uart_nextion_diagnostic_candidate_20261113.hex`.
SHA256 file di Pi cocok dengan build laptop.
**Image tidak di-flash dan tidak dijalankan
oleh ATmega**. File ini bukan firmware
E-Nose operasional.

QA source guard dan compilation PASS:
`python scripts/test_uart_nextion_diag_source.py`
dan `python scripts/test_pi_second_pcb_status_handshake.py`.
Kontrak RF30 startup dan build lain tidak diubah.

## 5. Keputusan teknis dan syarat menuju final fisik

**Komunikasi UART fisik belum FIX.**
Gagal memperoleh respons dari MCU melalui
UART0 dan bootloader; jalur UART2 Nextion
tidak dapat diukur langsung dari USB Serial0.
Kondisi Pi dan FT232R normal tidak
membuktikan firmware AVR berjalan.
Perbaikan source dan image yang dapat
dibangun di laptop **tidak dapat memperbaiki
perangkat fisik tanpa jalur pemrograman**.

Urutan yang sekarang dibutuhkan:

1. **Operator onsite:** pastikan
   RESET, clock dan rail ATmega benar,
   termasuk VCC/AVCC dan GND.
   Multimeter dapat memeriksa tegangan DC/
   RESET tetapi **tidak** dapat mendekode UART.
2. **Sediakan programmer ISP** yang kompatibel
   (mis. USBasp/Atmel-ICE) melalui jalur
   MOSI/MISO/SCK/RESET/GND dan tegangan
   referensi sesuai skematik. Jika tidak
   ada konektor/test point, perlu teknisi
   yang mampu mengakses jalur fisik.
3. Dengan persetujuan operator, baca signature
   ATmega2560 `0x1e9801`, baca **Flash dan
   EEPROM asli PCB kedua**, simpan hash
   dan pastikan backup/rollback valid.
   Jangan gunakan backup COM5/SVM30 dari PCB lain.
4. **Persetujuan flashing terpisah:**
   setelah backup dan daya terverifikasi,
   pilih uji terawasi image isolasi UART
   (jika pin valve-safe benar) untuk menentukan
   respons UART0, bukti kirim UART2 dan
   `sendme` LCD; kembalikan firmware produksi
   hanya setelah diagnosis dan QA selesai.
5. Saat MCU/Nextion berhasil, barulah
   integrasi RF500 30 siklus/900 sampel
   dijalankan dalam SOP terawasi.

**Stop condition: membutuhkan akses/reset/flash
hardware dan backup asli MCU.**
Tidak ada tindakan selanjutnya via Pi SSH saja
yang dapat membuktikan atau memperbaiki
jalur MCU yang tidak merespons tanpa
alat pemrograman/kontrol fisik tambahan.

RF500 di Pi tetap **staged, `live_activation_allowed=false`**.
Gerbang `pi_rf30_second_pcb_release_gate.py`
masih melaporkan `NO_GO_PHYSICAL_DEPLOYMENT`
karena signature programmer dan backup asli PCB kedua
belum tersedia.
