# RF500 listener permanen Raspberry Pi 5 — autostart, multi-AI Test, raw logging

**Tanggal:** 17 November 2026 WIB.
**Branch:** `wahyu`.
**Status:** listener permanen **RUNNING/READY**, boot entry terdaftar
dan diverifikasi; **belum dilakukan reboot fisik** dan belum ada AI Test
fisik baru menggunakan versi listener permanen.

## 1. Informasi eksperimen yang dikonfirmasi pengguna

Pada sesi RF500 live sebelumnya, ATmega2560 mengirim 900 sampel,
Pi memprediksi `light`, dan `AI_RESULT_ACK` MCU menyatakan `light`.
Pengguna kemudian mengonfirmasi bahwa **kopi asli adalah Light–Toraja
(L-TOR)**. Jadi **satu klasifikasi tersebut benar**.
Ini bukan estimasi akurasi statistik model.

## 2. Mengapa listener lama perlu diganti

Bridge benchmark `scripts/rf30_pi_result_bridge.py` hanya menangani
satu sesi dan keluar setelah `AI_RESULT_ACK`; waktu hidupnya
dibatasi 1260 detik. Mengulang proses untuk setiap AI Test
memerlukan SSH dan membuka FT232RL lagi. Rangkaian FT232RL
dapat memicu reset ATmega saat port dibuka.

Listener baru `scripts/rf500_pi_persistent_listener.py`:

- Membuka satu koneksi FT232RL `/dev/ttyUSB0`,
  mempertahankannya setelah prediksi selesai,
  dan otomatis membuat session state baru
  untuk **AI Test berikutnya**.
- Membaca `ACQ_START`, 900 sampel 30 siklus,
  `ACQ_COMPLETE`, `AI_AWAITING_RESULT`;
  hanya sesudah semua pemeriksaan valid,
  mengirim paket `#rf30:<TOKEN>:light|medium|dark;`.
- Menunggu `AI_RESULT_ACK` fisik untuk mencatat
  sesi berhasil; setelah ACK tidak menutup UART.
- Memakai model RF500 500 pohon yang telah
  diverifikasi SHA-256 dan versi scikit-learn terpin.
- Tidak memiliki perintah `#start`, `#stop`,
  `#scan`, kontrol pompa/valve, kalibrasi
  atau pengubahan Flash/EEPROM.
- Jika data sesi rusak atau tidak lengkap,
  membuang sesi tanpa mengirim prediksi;
  baru menerima sesi baru dengan `ACQ_START`
  yang memenuhi kontrak. Tidak membuka
  port ulang saat perbaikan state.
- Menyimpan seluruh frame mentah pengujian
  yang mendapat ACK sebagai NDJSON serta
  manifest JSON SHA256 di direktori privat Pi.
  **Log 900 sampel dari sesi L-TOR yang sudah
  berlalu tidak tersedia** karena listener lama
  belum mempunyai fitur ini.

QA offline:
`python scripts/test_rf500_pi_persistent_listener.py`
**PASS** untuk dua sesi 900 sampel berturut-turut
tanpa re-open serial dan untuk penolakan sesi
yang mengalami frame corrupt. Ini simulasi
protokol, bukan dua eksperimen kopi baru.

## 3. Autostart tanpa password administrator

Pi menggunakan user `enose-v3`. `cron.service`
sudah `enabled` dan `active`;
`sudo -n` tidak tersedia (membutuhkan password),
jadi tidak menambahkan systemd system-wide service.
Program dipasang dengan **crontab user**
`@reboot` yang tidak memerlukan `sudo`.

Entry tunggal yang terdaftar:

```text
@reboot /usr/bin/flock -n /home/enose-v3/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/cron.lock /bin/bash /home/enose-v3/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/rf500_pi_boot_supervisor.sh >> /home/enose-v3/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/supervisor.log 2>&1
```

Script `scripts/rf500_pi_install_autostart.py` mendukung
`--install` dan `--check`, memeriksa bahwa entry
tidak digandakan dan mempertahankan crontab lainnya.
Setelah registrasi, hasil `--check`:
`RF500_CRON_AUTOSTART_PRESENT`.
**Belum diverifikasi melalui reboot sungguhan.**

Wrapper `scripts/rf500_pi_boot_supervisor.sh`
memakai `flock` untuk satu instance,
menunggu nama FT232RL khusus `A10KMZQJ`
apabila belum tersedia saat boot, dan
mencoba ulang bila proses keluar dengan backoff
15/30/60/120 detik (mencegah reset port sangat sering).
Tidak menggunakan serial USB perangkat lain.

## 4. Jalur instalasi dan bukti aktif

Semua file pengguna pada Pi ditempatkan tanpa
menimpa staging bridge sebelumnya:

```text
/home/enose-v3/smart-coffee-stage7/rf30_staging/
  com4_integration_20261117/
    always_on/
      rf500_pi_persistent_listener.py
      rf500_pi_boot_supervisor.sh
      rf500_pi_install_autostart.py
      supervisor.log
      recordings/
```

Model tetap berada di direktori staging:
`final_model.joblib` dan `final_model_info.json`.
Serial target:
`/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0`
→ `/dev/ttyUSB0`.

Wrapper dijalankan melalui SSH menggunakan
`nohup /usr/bin/flock` dengan argumen
identik dengan crontab. Bukti sekitar 20.15 WIB:

```text
RF500_SUPERVISOR_START_ATTEMPT 1
RF500_PERSISTENT_READY {"baud":115200,
  "serial_open_once":true,"model_verified":true,
  "receiver_mode":"consecutive_30cycle_tests"}
fuser /dev/ttyUSB0 → PID 2675
vcgencmd get_throttled → throttled=0x0
```

## 5. Pemeriksaan operasi

Pantau logger:

```bash
tail -f ~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/supervisor.log
```

Cek serial sedang dipegang listener:

```bash
fuser /dev/ttyUSB0
crontab -l
```

**Penting:** listener permanen sekarang merupakan
pemegang port serial. Sebelum mengunggah firmware
ATmega, menggunakan serial monitor lain,
atau menjalankan receiver yang juga mengakses
`/dev/ttyUSB0`, hentikan supervisor saat
hardware sedang **IDLE**. Jangan menjalankan
dua proses pembaca serial bersamaan.

Pengujian selanjutnya dapat dilakukan dari Nextion
tanpa SSH manual dengan menekan **Start AI Test**.
Hasil tetap dibatasi pada roast Light/Medium/Dark;
coffee origin, kalibrasi R0, repeatability
dan akurasi statistik belum dibuktikan.
