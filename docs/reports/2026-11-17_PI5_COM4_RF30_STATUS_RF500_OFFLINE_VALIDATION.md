# Integrasi Raspberry Pi 5 dan E-Nose COM4 — UART berhasil, RF500 lulus replay offline

**Tanggal:** 17 November 2026 WIB.
**Cabang Git:** `wahyu`.
**Hardware:** PCB custom E-Nose dengan firmware RF30 yang di-flash dan di-verify melalui Windows **COM4** pada 17 November 2026, kini terhubung ke Raspberry Pi 5.

## 1. Identitas USB baru Raspberry Pi

- Pi SSH: `enose-v3@enose-pi5`, hostname `enose-pi5`.
- Windows COM4 sebelumnya: FT232RL VID:PID `0403:6001`,
  USB serial `A10KMZQJA`.
- Di Linux, jalur USB FT232RL:
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0`
  → `/dev/ttyUSB0`.
  Penanda `A` tambahan pada identifier Windows adalah penanda
  interface, bukan perangkat yang berbeda.
- Pi power: `vcgencmd get_throttled` → `throttled=0x0`;
  `EXT5V_V` sekitar **5,13–5,14 V**.
- `ModemManager` dan `serial-getty@ttyUSB0` tidak aktif.
  Pada pemeriksaan awal, tidak ditemukan proses yang memegang port
  `/dev/ttyUSB0`.
- Di Windows tidak ada COM4 setelah USB dicabut.
  Receiver Windows yang dipin ke serial target COM11 `A10KNJBLA`
  dibiarkan utuh (dan tidak melakukan akuisisi dari COM4).

## 2. RF500 yang sudah ada di Pi

Staging user sebelumnya tetap dipertahankan pada:
`~/smart-coffee-stage7/rf30_staging`.

`pi_rf30_pi5_readiness.py --expected-serial A10KMZQJ`
menghasilkan `HOST_STAGED_NOT_MCU_VERIFIED` dengan blockers kosong:

- `final_model.joblib` SHA-256
  `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`;
- Model `RandomForestClassifier`, **500 pohon**,
  kelas `dark/light/medium`;
- Tiga fitur ADC mentah:
  `tgs822_max_mean`,
  `tgs822_purging_mean_mean`,
  `mq8_max_mean`;
- Python 3.13.5 dan venv terisolasi: scikit-learn 1.7.2,
  numpy 2.5.4, scipy 1.18.1, joblib 1.6.0,
  pyserial 3.5;
- Script `roast_rf30_pi_inference.py`,
  `roast_rf30_pi_stream_replay.py`,
  `rf30_pi_result_bridge.py` tersedia.

Status `HOST_STAGED_NOT_MCU_VERIFIED` dari readiness itu
**bukan gagal**: script tersebut hanya memeriksa host dan tidak
membuka UART. Verifikasi MCU dilakukan terpisah di tahap berikutnya.

## 3. Handshake Pi ↔ ATmega secara fisik

Skrip baru di repo:
`scripts/pi_com4_rf30_status_handshake.py`.
QA mock `scripts/test_pi_com4_rf30_status_handshake.py` PASS.

Skrip tersebut dipindahkan ke folder baru pada Pi
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/`
bersama tiga skrip QA model offline. Folder staging lama, firmware MCU,
EEPROM, dataset, dan service tidak ditimpa.

Perintah yang telah dijalankan di Pi:

```bash
cd ~/smart-coffee-stage7/rf30_staging
.venv/bin/python com4_integration_20261117/pi_com4_rf30_status_handshake.py \
  --outdir com4_integration_20261117/handshake_01 --seconds 12
```

Satu perintah non-kontrol `#status;` dikirim, **8 byte TX**,
kemudian Pi menerima **1.459 byte RX**. Script menyiapkan
DTR/RTS LOW sebelum port dibuka, tetapi driver FT232RL
dapat menyebabkan reset transien saat open.

Hasil nyata:

```text
status = READ_COMPLETE
ftdi_serial = A10KMZQJ
uart_rx_bytes = 1459
fw_hello_seen = true
expected_firmware_build_id_observed = true
welcome_response_seen = true
system_ready_seen = true
ads1115_4_of_4_seen = true
calibration_missing_reported = true
no_acquisition_started = true
no_actuator_commands_sent = true
no_eeprom_or_flash_write = true
```

Firmware mengklaim `build_id=take30-ai30-rfhost-20261110`,
sesuai manifest kandidat RF30 yang sebelumnya
di-flash ke COM4 dengan AVRDUDE. Bukti ini
mengonfirmasi komunikasi UART dua arah,
**bukan** verifikasi ulang isi seluruh Flash dari Pi.

Log diagnostik disimpan **hanya di Pi**, pada
`com4_integration_20261117/handshake_01/{result.json,uart_raw.bin}`.
Port dilepas setelah tes, dan tidak ada proses
yang ditinggalkan memegang `/dev/ttyUSB0`.

## 4. Validasi RF500 di Raspberry Pi tanpa UART

Tiga pemeriksaan pada venv terisolasi Pi:

1. `pi_rf30_stage_model_verify.py`:
   `RF30_PI_MODEL_HASH_METADATA_PASS_NO_DESERIALIZATION`.
   Model hash/metadata/versi library cocok.
2. `pi_rf30_stage_selfcheck.py`:
   `RF30_PI_STAGED_MODULES_OFFLINE_PASS`.
   Framing, validasi startup session, token,
   dan error pada duplikasi JSON lolos tes.
3. `pi_rf30_stage_e2e_replay.py`:
   `RF30_PI_ACTUAL_MODEL_TO_UART_PACKET_OFFLINE_PASS`.
   Dataset rekaman `D-CAT_B70.csv`
   (`4800dcb0a5221430c2cb39c47fc6947ae123e1a7ffd1514ad32dc03b5b48f21c`)
   sebanyak 30 × 30 = **900 sampel** berhasil
   diproses menjadi prediksi roast `dark`.
   Paket `#rf30:B1F503A9:dark;` terbentuk
   dan MCU ACK **disimulasikan**. Tidak ada pengiriman UART.

Replay satu sampel terdata **bukan** metrik akurasi
model terhadap kopi baru. Label `dark` tidak
berarti perangkat fisik sudah mengklasifikasikan
kopi baru; origin dan confidence terkalibrasi
belum dihasilkan.

## 5. Perbedaan baseline HMI dan kalibrasi R0

Firmware pada `src/main.cpp`:
`EVT:CAL_START` dari halaman `pCal`
hanya merekam **60 sampel ADC udara bersih**
(`BASELINE_START ... eeprom_r0_modified:false`).
Proses ini **tidak mengubah EEPROM R0**.

Kalibrasi R0 yang sebenarnya melalui
`SensorArray::calibrate()` di `src/sensor.cpp`
hanya dipanggil ketika compile flag
`IS_CALIBRATING_GAS_SENSOR=1` dan memerlukan
SOP hardware/sensor clean-air terawasi.
Dalam firmware yang terpasang, startup melaporkan
R0 belum tersedia. **Tidak ada kalibrasi atau
penulisan EEPROM baru dalam sesi ini.**

Model RF500 saat ini memakai **tiga fitur raw ADC**,
tanpa baseline correction, R0 normalization,
atau global z-score. Karena itu nilai R0 kosong
tidak secara matematis menghalangi ekstraksi
fitur model tersebut, tetapi kestabilan
sensor dan relevansi data latih terhadap kondisi
hardware baru tetap harus divalidasi.

## 6. Gerbang menuju supervised AI Test fisik

**Yang sudah PASS:** FT232RL pada Pi, power Pi,
RF500 hash dan dependensi, dua arah perintah
status UART0, identitas firmware dari pesan boot,
4/4 ADS1115 terdeteksi, replay offline RF500.
User juga melaporkan Nextion sudah berada
di menu utama, tetapi foto/UI fisik dan
event tombol belum ditangkap secara langsung.

**Yang belum dilakukan:** menjalankan
`START AI TEST` 30 siklus (900 detik),
merekam data kopi baru,
memvalidasi kestabilan sensor,
mengirim prediksi RF500 dari Pi ke MCU,
membaca `AI_RESULT_ACK` dari MCU,
atau memverifikasi hasil di LCD.

Bridge `rf30_pi_result_bridge.py` yang sudah
tersedia memiliki dua opt-in untuk live bench:
`I_APPROVE_SUPERVISED_RF30_SERIAL_READ_WRITE` dan
`I_ACCEPT_UNVALIDATED_RF500_FOR_BENCH_ONLY`.
**Kedua opt-in belum diaktifkan dan tidak ada
daemon background yang dibuat.**

Sebelum aktivasi: lakukan pemeriksaan visual
hardware dan kondisi udara/kemasan kopi,
pastikan sensor stabil dan operator siap
mengawasi 30 siklus, pahami bahwa prediksi
RF500 masih eksperimental. Verifikasi
`pTestRun`, ACK MCU dan `pResult`
secara terpisah; jangan menyimpulkan dari
replay offline bahwa sistem end-to-end live
sudah lulus.
