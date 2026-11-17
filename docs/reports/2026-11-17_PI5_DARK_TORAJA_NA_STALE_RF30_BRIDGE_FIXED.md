# N/A pada AI Test Dark–Toraja — versi bridge Pi5 tidak kompatibel, sudah diperbaiki

**Tanggal:** 17 November 2026 WIB
**Branch:** `wahyu`
**Hardware:** E-Nose ATmega2560 custom, Nextion, Raspberry Pi 5, FT232RL USB serial
`A10KMZQJ` (`/dev/ttyUSB0`).

## 1. Gejala dan bukti awal

Operator menguji sampel baru **Dark–Toraja (D-TOR)** di Nextion,
dan halaman hasil menunjukkan **Roast level N/A**.
Listener permanen RF500 yang sebelumnya diaktifkan
sekitar **20.14 WIB** masih berjalan PID **2675**
dan memiliki `/dev/ttyUSB0` eksklusif.
Namun log `always_on/supervisor.log` hanya berisi:

```text
2026-11-17T20:14:52+07:00 RF500_SUPERVISOR_START_ATTEMPT 1
RF500_PERSISTENT_READY {...}
```

Tidak ada `ACQ_START`, hitungan siklus, 900 sampel,
hasil inferensi, `AI_RESULT_ACK`, atau file hasil
di `always_on/recordings`. Pada saat itu proses
masih hidup dan Pi `throttled=0x0`.
**Ini bukan bukti prediksi Dark salah;
belum ada prediksi model yang dijalankan.**

## 2. Memeriksa konektivitas MCU

Ketika sesi operator telah berakhir, listener
dan supervisor dihentikan secara terkontrol;
port dilepas tanpa flashing MCU. Tes non-kontrol
`#status;` dilakukan melalui FT232RL Pi5
dan menghasilkan **1457 byte RX**.

Hasil `pi_com4_rf30_status_handshake.py`:

```text
status = READ_COMPLETE
fw_hello_seen = true
expected_firmware_build_id_observed = true
welcome_response_seen = true
system_ready_seen = true
ads1115_4_of_4_seen = true
tx_bytes = 8
rx_bytes = 1457
no_acquisition_started = true
no_actuator_commands_sent = true
no_eeprom_or_flash_write = true
```

Lokasi bukti privat Pi:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/dark_toraja_diagnostics_status_01/`.
Kesimpulan terbatas: UART dua arah berfungsi setelah
port dibuka lagi; belum membuktikan kontinuitas
setiap byte selama tes Dark–Toraja sebelumnya.

## 3. Penyebab kesalahan yang terkonfirmasi

Kode listener `scripts/rf500_pi_persistent_listener.py`
memanggil:

```python
HostSession.feed(raw, allow_predict=True, predictor=predict)
```

Namun, pada instalasi Pi lama
`~/smart-coffee-stage7/rf30_staging/rf30_pi_result_bridge.py`,
API `HostSession.feed` **tidak memiliki argumen
`predictor`**. Berbeda dengan versi repo yang
telah diuji untuk RF500.

Karena `PersistentHandler.receive()`
menangkap `TypeError` generik saat belum ada
token sesi dan tidak mencetak alasan
penolakan sebelum `ACQ_START`, setiap frame
terbuang diam-diam, sementara proses
tetap menampilkan status READY.

Pada sesi diagnosis setelah instrumentasi log,
error muncul langsung saat startup:

```text
RF500_PRESTART_FRAME_REJECTED {
  "reason": "TypeError:HostSession.feed() got an unexpected keyword argument 'predictor'"
}
```

Inilah **akar masalah perangkat lunak yang
terkonfirmasi** dan konsisten dengan gejala N/A.
Tidak ada bukti bahwa model benar-benar
memprediksi N/A; model tidak dipanggil.

## 4. Perbaikan

1. Perbaiki diagnosa `rf500_pi_persistent_listener.py`
   dengan log event awal, frame sampel sebelum
   `ACQ_START`, penolakan frame dan heartbeat
   transport tiap 45 detik. Tetap tidak
   mengirim hasil bila sesi 900 frame invalid.
2. Tambah `verify_bridge_compatibility()` yang
   wajib memastikan file bridge berada **di
   direktori rilis yang sama** dengan listener,
   memiliki parameter `predictor` dan
   `BUILD_ID` sesuai firmware, sebelum membuka
   USB serial atau memuat model.
3. Salin versi bridge yang cocok ke:
   `~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/rf30_pi_result_bridge.py`.
   Versi staging lama tidak ditimpa.
4. Perbarui listener di direktori `always_on`
   dan tambahkan skrip validasi Pi read-only:
   `scripts/rf500_pi_verify_staged_bridge.py`.
5. Tambah tes regresi lokal yang memverifikasi
   bahwa API bridge salah **ditolak saat startup**,
   bukan mengakibatkan kegagalan diam-diam
   setelah 15 menit proses AI Test.

Checksum versi bridge yang benar:
`799a506c08f057667e81e9e40ae51a6b6059b435907482341945d299ab4acc71`.
Model RF500 tidak diubah; SHA:
`b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.

## 5. Verifikasi setelah perbaikan

Pada Pi, pemeriksaan read-only dalam venv
RF500 yang sama menghasilkan:

```text
PERSISTENT_BRIDGE_AND_MODEL_READ_ONLY_PREFLIGHT_PASS
api_predictor_param = true
bridge_module = .../com4_integration_20261117/always_on/rf30_pi_result_bridge.py
serial_opened = false
model_deserialized = false
```

QA lokal dua sesi berturut-turut dengan
900 sampel, input rusak, frame tanpa
`ACQ_START`, serta penolakan API lama: **PASS**.

Replay offline pada Pi menggunakan modul
yang baru disalin dan data contoh
`D-CAT_B70` (bukan Dark–Toraja)
memproses 900 sampel menjadi prediksi
`dark` dan paket hasil `#rf30:B1F503A9:dark;`.
ACK pada replay ini **simulasi**, bukan
hasil pengujian kopi baru.

Listener permanen kemudian dijalankan
ulang menggunakan autostart supervisor
yang sama. Sekitar **20.50 WIB**:

```text
PID 3174 memegang /dev/ttyUSB0
RF500_PERSISTENT_READY
RF500_PRESTART_FIRMWARE_EVENT FW_HELLO
RF500_TRANSPORT_HEARTBEAT {
    "rx_bytes_total": 991,
    "rx_frames_total": 17,
    "prestart_start_rejections": 0,
    "successful_sessions": 0
}
vcgencmd get_throttled = throttled=0x0
```

Tidak ada `TypeError` pada proses baru.
Autostart `cron @reboot` tetap ada.
Belum ada pengujian Dark–Toraja
ulang setelah rilis perbaikan ini.

## 6. Tindak lanjut

Pengguna dapat menguji **Dark–Toraja** lagi
melalui Start AI Test pada Nextion karena
listener yang cocok sudah READY.
Untuk pembuktian berikutnya perlu melihat
`RF500_LIVE_CAPTURE_STARTED`, 30 kali
`RF500_CYCLE_COMPLETE`, hasil
`RF500_RESULT_SENT_AWAIT_MCU_ACK`,
dan `RF500_MCU_ACK_CONFIRMED`.
Jika tercatat error berbeda, gunakan
heartbeat dan log diagnostik baru
tanpa membuat asumsi bahwa model salah.

Karena versi listener sebelumnya tidak
menyimpan data pada sesi yang gagal,
900 frame sensor pengujian Dark–Toraja
pertama tidak dapat direkonstruksi dari
log progres yang ada.
