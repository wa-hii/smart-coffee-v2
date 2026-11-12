# PCB kedua — AVRDUDE bootloader signature timeout, RF500 deployment ditahan

Tanggal: 12 November 2026, sekitar 17:02–17:07 WIB. Branch: `wahyu`.

## 1. Ruang lingkup

Operator menegaskan PCB kedua berada dalam kondisi fisik aman dan meminta pekerjaan dilanjutkan sampai final. Perangkat yang diperiksa **bukan** PCB ATmega2560 yang pada 11 November pernah di-flash melalui COM5 Windows. Jalur aktif adalah `enose-v3@enose-pi5` (SSH/Tailscale) → FT232R serial `A10KNJBL` → PCB kedua; Nextion sebelumnya dilaporkan tertahan pada `Initializing Systems`. Tidak ada bukti bahwa firmware SVM30 lama terpasang pada PCB kedua.

Tujuan: memverifikasi jalur bootloader/programmer, membaca signature, lalu melakukan backup Flash dan EEPROM asli sebelum mempertimbangkan penggantian firmware.

## 2. Pemeriksaan sebelum membuka port

- SSH berhasil; `vcgencmd get_throttled=0x0`, `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0` → `../../ttyUSB0`.
- `fuser /dev/ttyUSB0` tidak menunjukkan proses pemilik port.
- Kernel mencatat FT232R sempat **disconnect pada 17:01:11 WIB dan reconnect 17:01:12 WIB**, *sebelum* percobaan AVRDUDE. Penyebab disconnect tersebut belum diketahui.
- Account SSH tidak memiliki `sudo -n`. Paket `avrdude` Debian 7.1 arm64 dan tiga pustaka dependensi diunduh kemudian diekstraksi di folder **terisolasi milik user** di staging Pi, tanpa menginstal paket sistem. `ldd` menemukan seluruh pustaka dan binari AVRDUDE berhasil dijalankan.

Folder tool lokal Pi:

`/home/enose-v3/smart-coffee-stage7/rf30_staging/second_pcb_20261112_bootguard_v1/toolchain/extracted/`

## 3. Satu percobaan membaca signature

Perintah dijalankan melalui SSH dengan timeout total 20 detik, variabel `LD_LIBRARY_PATH` menunjuk library lokal, AVRDUDE 7.1 dengan:

```text
-p m2560 -c wiring -P /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0 -b 115200 -n -v
```

`-n` dipakai untuk menghindari operasi tulis; **tidak ada `-U flash:w`, `-U eeprom:w`, fuse write, chip erase atau upload**. Jalur `wiring`/115200 merupakan **kandidat berdasar board sebelumnya**, bukan bootloader yang sudah dikonfirmasi untuk PCB kedua.

**Hasil:**

- Tiga baris `avrdude stk500v2_recv() error: timeout`.
- Exit code **124** (dihentikan oleh pembatas waktu 20 detik).
- **Signature chip tidak diterima.**
- **Backup Flash dan EEPROM PCB kedua tidak dapat dimulai.**
- Tidak dilakukan percobaan bootloader lain atau auto-retry untuk menghindari reset berulang dan potensi gangguan USB.

Pembukaan port AVRDUDE dapat menyebabkan reset DTR tergantung jalur PCB. Tidak ada pengukuran langsung yang membuktikan apakah reset benar-benar mencapai MCU.

## 4. Pemeriksaan setelah percobaan

- Pada pemeriksaan sekitar 17:06:48 WIB, SSH tetap terhubung, `get_throttled=0x0`, dan by-id FT232R tetap menunjuk `ttyUSB0`.
- `fuser` tidak menemukan pemilik port.
- Journal kernel tidak menemukan `xHCI host controller not responding` baru ataupun USB disconnect baru setelah koneksi ulang 17:01.
- Model RF500 Pi `final_model.joblib` SHA256 `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d` tetap cocok.
- Firmware RF30 bootguard tersimpan di staging Pi dengan SHA256 `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`. Tidak di-upload.
- `pi_rf30_pi5_readiness.py`: `HOST_STAGED_NOT_MCU_VERIFIED`, `live_activation_allowed=false`.
- Tidak ada `/dev/spidev*` pada Pi; hal itu tidak membuktikan hardware ISP tidak ada, tetapi tidak tersedia perangkat SPI pengguna yang siap digunakan.

## 5. Interpretasi dan keputusan

**NO-GO untuk flashing RF30 pada PCB kedua.** Tidak adanya respons STK500v2 tidak dengan sendirinya membuktikan MCU rusak. Kemungkinan termasuk bootloader yang berbeda/tidak tersedia, DTR/RESET tidak tersambung, jalur RX/TX terbalik/terputus, konflik level/ground, atau firmware/perangkat keras tertahan. Tidak ada pengukuran yang cukup untuk memilih penyebab. Gejala Nextion `Initializing Systems` juga belum dituntaskan.

Backup firmware/EEPROM dan rollback SVM30 **PCB lama** tidak boleh dipakai sebagai backup **PCB kedua**.

Gerbang selanjutnya perlu bukti fisik penomoran net Serial0 TX/RX, GND, DTR/RESET, tegangan/level FT232R, bootloader dan akses ICSP (MISO/MOSI/SCK/RESET/5V/GND). Dengan programmer ISP yang benar dan SOP aman, baca signature serta backup Flash/EEPROM **khusus PCB kedua**, verifikasi checksum dan jalur rollback, baru dapat mempertimbangkan satu upload RF30. Setelah itu dibutuhkan uji boot `pHome`, streaming 30 siklus/900 sampel, ACK hasil AI nyata, dan evaluasi Light/Medium/Dark pada perangkat baru.

Tidak ada perintah aktuator, kalibrasi, upload TFT/HMI, chip erase, atau penulisan Flash/EEPROM pada sesi ini.
