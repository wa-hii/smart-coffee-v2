# Raspberry Pi 5 E-Nose: auto-save Take Data + RF500 dalam satu listener, auto-login boot

**Tanggal:** 19 November 2026 WIB. **Branch:** `wahyu`.
**Perangkat:** `enose-v3@enose-pi5` (Pi 5 pertama),
FT232RL `A10KMZQJ` → `/dev/ttyUSB0`, ATmega2560
firmware `take30-ai30-rfhost-20261110` dan HMI Nextion.

## Masalah awal: lima pengambilan data dibuang dari jalur penyimpanan

Operator menggunakan menu **Take Data** pada Nextion saat Pi
menjalankan listener permanen `rf500_pi_persistent_listener.py`
yang pada saat itu hanya menerima protokol `ai_test`.
Log Pi menunjukkan **5 `ACQ_START mode=labeled_data`**
dan total **4.500 frame sensor** dengan
`RF500_SENSOR_FRAME_WITHOUT_ACQ_START`,
tetapi listener lama menolak setiap start dengan
`start_contract_wrong_firmware_or_mode`.

Log status/progres bukan log ADC mentah untuk tiap frame.
Tidak ada CSV baru untuk lima sesi tersebut yang
dapat direkonstruksi lengkap dari log lama. Folder
`~/smart-coffee-stage7/data/raw` sebelumnya hanya
memiliki file legacy `D-GAW_B33.csv` (11 Oktober),
dan **lima pasang AI Test rekaman NDJSON/JSON
18 November** tetap ada di folder
`rf30_staging/com4_integration_20261117/always_on/recordings/`.
Jangan memperlakukan 4.500 frame yang hanya dihitung
di log sebagai data CSV yang sudah tersimpan.

## Perbaikan: satu UART, dua mode

Ditambahkan `scripts/pi_labeled_take_data.py` dan
integrasi dalam `scripts/rf500_pi_persistent_listener.py`.
Serial FT232RL tetap **dimiliki satu listener saja**.
Take Data tidak memanggil model, tidak mengirim perintah
USB ke ATmega, tidak mengendalikan aktuator dan tidak
menyentuh EEPROM/Flash.

Saat operator menekan **Start Take Data** di Nextion,
firmware mengirim `ACQ_START` berisi:
`mode=labeled_data`, `sample_id`, `roast_level`,
`origin_code`, `batch_id`, `filename`,
`fw_build_id`, `cycles_total=30`, `purge_s=25`,
`collect_s=5`, `total_samples_expected=900`.

Receiver memvalidasi metadata (termasuk konsistensi
L/M/D, origin dan filename) dan setiap sampel dengan
urutan **30 × (25 purging + 5 collecting)**,
`cycle`, `sample_idx`, timestamp monoton,
10 ADC 0–32767, suhu serta kelembapan (kosong
diizinkan jika sensor environmental tidak tersedia).
Setiap sampel ditulis dan `fsync` ke berkas
`.partial.csv` di `data/raw/.incoming/`.

Setelah `ACQ_COMPLETE` dan tepat **900 baris**,
file dipublikasikan secara atomik ke folder
`data/raw` memakai hardlink eksklusif, tanpa
menimpa CSV lama; dibuat sidecar JSON yang
memuat hash SHA256, label, waktu, dan jumlah
pembacaan environmental yang hilang.
Kolom CSV kompatibel dengan struktur dataset:

```text
timestamp,sample_id,roast_level,origin,batch_id,run_id,phase,sample_idx,
adc_tgs822,adc_mq135,adc_mq3,adc_tgs2611,adc_tgs2620,
adc_tgs2600,adc_tgs2602,adc_mq8,adc_tgs813,adc_tgs816,
temperature,humidity
```

Nilai `origin` di CSV disimpan sebagai **kode Nextion**
(mis. `TOR`), tanpa mengarang nama varian kopi yang
tidak ada di UART. Manifest juga menyimpan `origin_code`.

Bila serial corrupt, fase/sampel hilang, sesi dibatalkan,
MCU restart, timeout tanpa data selama 12 detik atau
`ACQ_COMPLETE` tidak sesuai, file parsial dipindahkan
ke **`data/raw/incomplete/`** dan tidak dianggap
data valid untuk training.
File `.incoming/*.partial.csv` yang tertinggal akibat
mati mendadak juga dikarantina pada startup berikutnya.

Untuk **AI Test**, pengolahan RF500, validasi 900 sampel,
`#rf30:<token>:roast;`, verifikasi `AI_RESULT_ACK`,
dan penyimpanan NDJSON AI yang terdahulu tetap berlaku.

## QA tanpa mengubah perangkat fisik

**Windows/offline**:

- `python scripts/test_pi_labeled_take_data.py`:
  dua sesi 900 sampel berturut-turut,
  nama unik/no-overwrite, CSV 20 kolom,
  incomplete 899-sampel, timeout,
  recovery parsial saat boot, dan
  jalur AI existing tetap terpisah: **PASS**.
- `python scripts/test_rf500_pi_persistent_listener.py`:
  dua AI Test berurutan, fail-closed, USB identity,
  dan bridge API compatibility: **PASS**.
- `python scripts/test_rf30_pi_result_bridge.py`:
  kontrak MCU/result RF30: **PASS**.

**Pi5/offline dari rekaman fisik lama**:

- Skrip `scripts/pi_take_data_offline_replay.py`
  membaca **900 data sensor nyata** dari rekaman
  AI Test tersimpan; membuat header `labeled_data`
  **sintetis dalam `TemporaryDirectory` saja**.
- Hasil: `PI_TAKE_DATA_REAL_SENSOR_REPLAY_OFFLINE_PASS`,
  900 baris, 30 siklus, CSV/checksum
  `474ad4122cd8d8c861fabc14258cfb2936d109bf19eeaea971886fe77cecd9f9`.
- Label sintetis **tidak disimpan sebagai
  dataset pelatihan**, semua file temp dihapus,
  tanpa USB open/UART TX dan tanpa model di-load.

## Aktivasi langsung pada Pi5

Sebelum penggantian, listener PID 841
memegang `/dev/ttyUSB0` tetapi
`last_rx_age_s` sudah lebih dari 900 detik,
`active_capture=false`, dan Pi
`vcgencmd get_throttled=0x0`.

Backup versi listener lama disimpan di:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/backup_before_take_20261119/`.
Versi baru dan modul recorder ditempatkan di
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/`;
SHA256 setelah SCP dicocokkan dengan sumber:

- `rf500_pi_persistent_listener.py`:
  `0f48823cbcd90d2788ff6b409f5ef3b8827d11d07d0c7a4b9ccde280648f0a43`
- `pi_labeled_take_data.py`:
  `6180cfe9ccdf301ae9c6252143ef720a7e1ec1b8a925534b4d117e9bdbdc59ec`

Proses lama dihentikan sekali saat IDLE dengan
SIGTERM, supervisor boot yang sudah ada
menjalankan ulang listener **tanpa perubahan crontab**.
Pada pemeriksaan Pi pukul sekitar 17.42 WIB,
listener baru **PID 2362** memegang `/dev/ttyUSB0`
dan log menunjukkan:

```text
RF500_SUPERVISOR_START_ATTEMPT 2
TAKE_DATA_RECOVERY_STARTUP {
  "previous_partial_files_quarantined": 0,
  "take_data_csv_root": "/home/enose-v3/smart-coffee-stage7/data/raw"
}
RF500_PERSISTENT_READY
RF500_PRESTART_FIRMWARE_EVENT FW_HELLO
```

Setelah restart belum dijalankan **pengujian fisik baru**
menu Take Data 30 siklus, sehingga statusnya adalah
**listener ACTIVE, recorder OFFLINE-VALIDATED,
physical new CSV pending**.

## Otomatis login dan keamanan

User meminta agar setelah reboot Pi tidak meminta
password untuk menjalankan alat. Pemeriksaan read-only
menemukan **auto-login sudah aktif**:

- `/etc/systemd/system/getty@tty1.service.d/autologin.conf`
  berisi `agetty --autologin enose-v3`;
  proses login lokal berjalan.
- `/etc/lightdm/lightdm.conf`
  berisi `autologin-user=enose-v3`;
  `lightdm.service` aktif.
- `cron.service` aktif dengan user crontab
  `@reboot` mengaktifkan listener,
  **tidak bergantung pada login interaktif**.

Karena tidak perlu, **password akun Linux tidak
dikosongkan**, SSH tidak dijadikan passwordless,
dan tidak ada perubahan `sudo`/PAM.
Tidak dilakukan reboot fisik selama pengambilan
data pengguna; setelah boot berikutnya,
status listener tetap perlu dicek secara nyata.

## Operasi sehari-hari

CSV final:
`/home/enose-v3/smart-coffee-stage7/data/raw/<sample_id>_<batch_id>.csv`
atau nama unik bila ada duplikat.

Incomplete:
`/home/enose-v3/smart-coffee-stage7/data/raw/incomplete/`

Log:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/supervisor.log`.

Saat Take Data selesai dengan sukses,
log harus menampilkan `TAKE_DATA_CSV_SAVED_900_VALID`;
file final dan sidecar JSON bisa diperiksa.
Jangan buka serial monitor kedua saat listener aktif.
