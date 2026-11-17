# AI Test E-Nose COM4 → Raspberry Pi 5 RF500 → Nextion: hasil Light, ACK fisik PASS

**Tanggal:** 17 November 2026 WIB, sesi selesai sekitar 19.59 WIB.
**Branch Git:** `wahyu`.

## Konfigurasi pengujian

- PCB E-Nose ATmega2560 custom yang sebelumnya di-flash dari
  Windows COM4, FT232RL serial `A10KMZQJA`,
  kini pada Raspberry Pi 5 sebagai
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0`
  → `/dev/ttyUSB0`.
- Firmware MCU `take30-ai30-rfhost-20261110`, LCD Nextion Serial2 9600.
- Model host `final_model.joblib`: Random Forest 500 pohon,
  dengan fitur `tgs822_max_mean`, `tgs822_purging_mean_mean`,
  `mq8_max_mean`.
  SHA256 model `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
- Listener Pi5 `rf30_pi_result_bridge.py`, PID 2264,
  dinyalakan sebelum pengujian fisik.
- Pengguna menekan Start AI Test melalui Nextion dan
  melaporkan hasil akhirnya **Light**.

## Bukti log real Raspberry Pi

Lokasi log asli:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/live_rf500_01/listener.log`.
Log disimpan di Pi, tidak di-push ke Git.

```text
RF30_SERIAL_LISTENER_READY_SUPERVISED
RF30_LIVE_CAPTURE_STARTED_30_CYCLES
RF30_LIVE_CYCLE_COMPLETE 1/30
...
RF30_LIVE_CYCLE_COMPLETE 30/30
RF30_LIVE_CAPTURE_COMPLETE
RF30_LIVE_RESULT_READY_FOR_SUPERVISED_TX
{"status": "SUPERVISED_RF30_MCU_ACK", "roast": "light", "samples": 900, "serial_tx": true, "lcd_visual_confirmed": false}
```

Bridge menegakkan validasi **30 × (25 detik purging +
5 detik collecting)** = **900 sampel**.
Hasil tidak dikirim sebelum `ACQ_COMPLETE` dan
`AI_AWAITING_RESULT` lolos pemeriksaan token serta
jumlah sampel. Log `SUPERVISED_RF30_MCU_ACK`
adalah ACK fisik yang diterima dari ATmega,
**bukan** simulasi replay.

**Hasil:** Pi menghitung roast `light`, mengirim
hasil ke ATmega, menerima ACK `light`,
dan operator melihat roast level Light pada Nextion.
`lcd_visual_confirmed:false` hanya menandakan
Pi tidak memverifikasi tampilan fisik melalui kamera.

## Kondisi sesudah tes

- Pemeriksaan SSH sekitar **20.01 WIB**:
  PID 2264 telah berhenti (exit normal sesudah ACK);
  `/dev/ttyUSB0` tidak sedang dimiliki proses.
- FT232RL tetap terdeteksi pada Pi;
  `vcgencmd get_throttled` menghasilkan `throttled=0x0`.
- Tidak ada upload firmware, kalibrasi atau
  penulisan EEPROM selama tes ini.
- Pompa dan valve dijalankan oleh firmware
  pada proses AI Test yang dipicu melalui Nextion;
  bridge Pi tidak mengeluarkan perintah pengendali aktuator.

## Batas kesimpulan

**Integrasi fungsional end-to-end PASS untuk satu sesi**:
Nextion → ATmega akuisisi → Raspberry Pi RF500 →
ATmega ACK → Nextion menampilkan hasil.

**Belum berarti akurasi model PASS:** label roasting
sebenarnya sampel fisik belum diberikan operator,
dan satu tes belum mengukur repeatability atau
generalisasi terhadap sampel, batch, dan origin lain.
Prediksi `origin` dan probabilitas terkalibrasi
belum tersedia pada bridge ini.

Listener saat ini hanya menyimpan progres dan hasil
akhir ke log, **bukan 900 frame raw sensor** ke CSV.
Bila membutuhkan analisis grafik sensor dari pengujian
AI Test ini, logging raw harus ditambahkan dan diuji
sebelum sesi berikutnya.

Firmware sebelumnya melaporkan R0 kalibrasi EEPROM
belum tersedia. RF500 menggunakan fitur ADC mentah,
namun sensor dan kesesuaian data pelatihan masih perlu
divalidasi secara eksperimen.

## Tindak lanjut

1. Catat sampel fisik yang diuji (roast level asli,
   origin, batch dan pengulangan) untuk membandingkan
   prediksi `light` dengan ground truth.
2. Lakukan beberapa pengulangan sampel yang diketahui
   berlabel Light/Medium/Dark dan buat confusion matrix.
3. Tambahkan penyimpanan aman 900 frame raw pada
   listener Pi sebelum melakukan pengujian berikutnya.
   Listener harus dijalankan ulang untuk sesi AI Test baru.
