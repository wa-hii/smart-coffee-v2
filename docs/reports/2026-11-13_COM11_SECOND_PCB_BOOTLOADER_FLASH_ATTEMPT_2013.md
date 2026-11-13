# Hasil akses COM11, build RF30, uji bootloader dan keputusan flashing PCB kedua

**Tanggal:** 13 November 2026, sekitar 20.10–20.16 WIB
**Branch kerja:** `wahyu`
**Target:** PCB ATmega2560 kedua dengan FT232RL onboard yang saat ini tersambung ke laptop Windows melalui **COM11**
**Status akhir:** **TIDAK ADA FLASH** — belum ditemukan jalur pemrograman yang merespons.

## 1. Identitas USB yang benar-benar terbaca

```text
COM11
USB Serial Port (COM11)
VID:PID = 0403:6001
USB serial menurut pyserial Windows = A10KNJBLA
PnP device status = OK
```

Windows menambahkan suffix antarmuka `A` pada identitas port FTDI,
sementara saat dipasang di Pi perangkat ini ditemukan sebagai
`A10KNJBL`. Target ini merupakan PCB kedua, **bukan** perangkat COM5
atau firmware/backup SVM30 dari PCB lama.

Sebelum pengujian tidak ada proses `lcd_acquisition_service.py`
atau `avrdude.exe` yang menggunakan port; direktori akuisisi
`data/raw/.incoming` kosong. Hanya terdeteksi USB FTDI;
tidak ada USBasp/Atmel-ICE/AVRISP pada perangkat Windows yang
terenumerasi.

**Batas:** enumerasi COM11 adalah bukti USB bridge berfungsi,
bukan bukti pin TXD/RXD atau DTR dari FT232RL mencapai ATmega2560,
firmware MCU berjalan, ataupun bootloader MCU ada.

## 2. Build yang berhasil

Build langsung dari checkout pada sesi ini:

```text
pio run -c scripts/platformio_rf30_bench.ini -e rf30_return_bench
SUCCESS; program 35770 byte; RAM statis 3917 byte.

SHA256 .pio/build/rf30_return_bench/firmware.hex
26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6

SHA256 kandidat privat rf30_pi_return_candidate.hex
26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6

HASH_MATCH = True
```

Perhatian: firmware RF30 kandidat mengaktifkan
`ENABLE_PI_RF30_RETURN=1`, menggunakan boot I²C berbatas
`Wire.setWireTimeout`, dan memerlukan bridge Pi untuk
prediksi roast. **Build berhasil tidak membuktikan perangkat
sudah siap menjalankan firmware ini**. Model RF500 sendiri
belum dinyatakan layak live end-to-end.

Firmware isolasi UART/Nextion juga build PASS:
`pio run -c scripts/platformio_uart_nextion_diag.ini
-e uart_nextion_diag`, Flash 4750 byte, RAM 426 byte,
SHA256 `87be0d01364f170190204be05e8310a2b920dea077d34380520c0ce75254c936`.
Ini **hanya kandidat compile-only**, tidak di-upload.

## 3. Percobaan akses bootloader COM11 langsung

Perintah read-only pertama yang dijalankan oleh
`scripts/com11_rf30_verified_deploy.py`:

```text
avrdude -C avrdude.conf -p m2560 -c wiring -P COM11 -b 115200 -n -v

Using Port : COM11
Using Programmer : wiring
Overriding Baud Rate : 115200
stk500v2_ReceiveMessage(): timeout
TIMEOUT_KILLED
```

AVRDUDE dibatasi maksimal 20 detik dan keluar dengan
`BOOTLOADER_SIGNATURE_NOT_VERIFIED_NO_FLASH`
(exit code 3 dari prosedur). Karena
`Device signature = 0x1e9801` tidak pernah didapat,
prosedur **tidak menjalankan tahapan backup
Flash/EEPROM maupun perintah upload**.

Bukti privat yang tidak masuk Git:
`private/com11_second_pcb_deployment/20261113_201319_604041/`,
termasuk `01_bootloader_probe.log`, argumen tool dan
`release_result.json`.

Beberapa percobaan sebelumnya juga telah menguji
`arduino/115200` dan `wiring/57600` tanpa signature.
Tidak dilakukan pemindaian baud/bootloader berulang tanpa dasar.

## 4. Uji satu pulsa DTR untuk menangkap penanda boot

Kode baru:
`scripts/com11_single_dtr_boot_capture.py`,
QA: `scripts/test_com11_single_dtr_boot_capture.py`.

Setelah identitas port dan guard aktivitas terverifikasi,
port dibuka pada 115200 baud dengan DTR/RTS mula-mula
False, kemudian **DTR diassert satu kali selama 140 ms**
dan dilepas. Ini *mungkin* memicu reset AVR jika
jalur DTR# FT232RL ke RESET AVR melalui rangkaian
auto-reset yang benar memang ada.
Pembacaan RX selama 12 detik dilakukan tanpa
menulis byte ke UART. Glitch yang timbul akibat
driver sewaktu open tetap tidak bisa disingkirkan.

**Hasil hardware:**

```text
status=RX_COMPLETED
port=COM11
dtr_pulse_count=1
uart_tx_bytes=0
rx_bytes=0
fw_hello_seen=false
bootloader_signature_verified=false
flash_written=false
eeprom_written=false
```

Data mentah benar-benar kosong, SHA256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Log privat berada di
`private/com11_second_pcb_deployment/dtr_boot_capture_*/`.

**Interpretasi yang aman:** tidak ada penanda yang membuktikan
pulsa DTR mencapai RESET AVR atau `FW_HELLO` dikirim.
RX 0 byte bukan bukti bahwa MCU pasti mati/bootloader
terhapus: rangkaian reset, level tegangan, UART0,
clock, source berbeda, atau firmware yang sengaja
diam tetap merupakan kemungkinan.

## 5. Kesimpulan masalah dan batas tindakan

**Bukti kuat:**

1. COM11 dapat diakses dan FT232RL USB berjalan.
2. Firmware RF30 dibangun ulang dan hash cocok.
3. Programmer `wiring/115200` tidak memperoleh
   signature saat perintah read-only.
4. Pulsa DTR dari driver tidak menghasilkan pesan
   UART0 yang dapat diamati.
5. Tidak ada backup Flash/EEPROM PCB kedua yang valid.

**Belum terbukti:** apakah ATmega terhubung ke FT232RL
melalui UART0 yang benar; apakah DTR# diarahkan ke
RESET; apakah MCU memiliki bootloader yang sesuai;
apa firmware lama MCU; apakah MCU sudah menjalankan
`Serial2` untuk Nextion. Tidak ada file HMI yang
diunggah maupun ditulis ulang.

Tanpa komunikasi bootloader yang terbukti atau
akses ISP, **tidak mungkin mengunggah firmware
ke chip ini hanya dengan mengganti port COM atau baud**.
Menganggap status upload sebagai PASS adalah salah.

## 6. Jalur terukur untuk mencapai flashing sesungguhnya

1. Operator **mematikan seluruh sumber daya dengan aman**,
   memastikan tegangan pada rangkaian nol,
   dan memeriksa secara continuity titik jalur
   **FT232RL TXD → ATmega RXD0/PE0**,
   **FT232RL RXD ← ATmega TXD0/PE1**, dan GND.
   Gunakan titik uji/skematik PCB, bukan menebak
   kaki IC yang berdekatan. DTR# menuju RESET
   mungkin melalui kapasitor sehingga tidak
   dapat dinilai dengan continuity DC biasa.
2. Jika bootloader tidak merespons,
   sediakan **programmer ISP fisik**
   (USBasp/Atmel-ICE/AVRISP) dan sambungkan
   SPI MISO/MOSI/SCK, RESET, GND, serta
   tegangan referensi sesuai programmer
   dan catu PCB. **Jangan menjumper sumber 5 V
   berbeda tanpa analisis power path**.
3. Setelah programmer enumerasi, lakukan
   identifikasi signature ATmega2560
   `0x1e9801` secara baca-saja;
   baca backup **Flash, EEPROM, fuses/lockbits**
   PCB kedua dan verifikasi integritas/hash
   sebelum operasi tulis. Verifikasi adanya
   prosedur restore asli yang realistis.
4. Dengan persetujuan onsite, pilih apakah
   perlu memulihkan bootloader melalui ISP
   atau langsung menjalankan image diagnostik.
   **Setelah backup**, gunakan image UART–
   Nextion terpisah secara terawasi untuk
   membuktikan `UART_DIAG BOOT`, `#status;`,
   `page pHome`, dan balasan `sendme`
   dari Nextion. Firmware ini perlu
   verifikasi fisik pin D10/D11 aman.
5. Baru setelah link UART0/UART2 dan
   pemulihan perangkat stabil, tentukan
   firmware produksi RF30 yang disetujui,
   upload/verify dan validasi model RF500.

**Stop condition:** identitas MCU dan backup
Flash/EEPROM PCB kedua tidak tersedia,
sedangkan bootloader UART terus timeout.
Saat ini **STOP sebelum flash**; tidak ada
perintah menulis firmware/EEPROM.

## 7. QA software

`test_com11_active_target.py`,
`test_com11_rf30_verified_deploy.py`,
`test_com11_alternative_bootloader_probe.py`,
`test_com11_single_dtr_boot_capture.py`:
semuanya PASS dalam pengujian yang relevan.
QA mock yang mensimulasikan upload sukses
**bukan bukti perangkat fisik sudah terprogram**.
Seluruh log asli disimpan di `private/` dan
tidak ditambahkan ke Git.
