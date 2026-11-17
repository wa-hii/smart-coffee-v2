# RF500 live listener Raspberry Pi 5 — siap menerima AI Test fisik dari Nextion

**Tanggal:** 17 November 2026 WIB
**Branch Git:** `wahyu`
**Status teramati:** `RF30_SERIAL_LISTENER_READY_SUPERVISED` — listener aktif dengan PID `2264`.

## 1. Kondisi sebelum aktivasi

- Operator telah menghentikan AI Test sebelumnya dan mengonfirmasi
  bahwa LCD Nextion sudah kembali ke halaman menu.
- Perangkat E-Nose FT232RL dari Windows COM4 (USB serial `A10KMZQJA`)
  tersambung pada Raspberry Pi 5 sebagai
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0`
  → `/dev/ttyUSB0`.
- Tidak ada pemegang serial sebelumnya; power Pi
  `vcgencmd get_throttled` menunjukkan `throttled=0x0`.
- Model `final_model.joblib` 500 pohon SHA-256
  `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`
  serta metadata dan modul bridge tersedia di venv terisolasi.
- Perintah `#status;` sebelumnya sudah dibalas oleh ATmega,
  dan firmware mengklaim build-id `take30-ai30-rfhost-20261110`.

## 2. Percobaan listener pertama dan penyebab kegagalan

Listener lama dijalankan untuk uji live di Pi, tetapi setelah
menampilkan `RF30_SERIAL_LISTENER_READY_SUPERVISED`
langsung berhenti dengan:

```text
ReturnProtocolError: invalid_or_oversized_serial_frame
```

Kegagalan terjadi sebelum sesi AI Test baru dimulai,
karena program masih menolak byte NUL/binary startup
yang mungkin muncul akibat pembukaan port FT232RL.
Log percobaan pertama disimpan privat:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/live_rf500_01/startup_failed_prev.log`.
Tidak ada paket prediksi dikirim ke MCU pada percobaan gagal tersebut.

## 3. Perbaikan dengan integritas sesi ketat

File `scripts/rf30_pi_result_bridge.py` diperbaiki:

- `HostSession.feed` boleh mengabaikan **maksimal delapan**
  frame berisi NUL, oversized, atau UTF-8 tidak valid
  **hanya sebelum** `ACQ_START` yang valid.
- Setelah `ACQ_START`, kesalahan frame tetap fatal
  sehingga tidak ada imputasi atau inferensi dari
  sesi yang berisi data rusak.
- Jika noise sebelum sesi berulang lebih dari delapan
  frame, listener berhenti secara fail-closed.
- Listener menampilkan `RF30_LIVE_CAPTURE_STARTED_30_CYCLES`,
  `RF30_LIVE_CYCLE_COMPLETE <n>/30`, dan
  indikator akhir sesi di log; pencatatan progres
  tidak mem-bypass syarat 900 sampel atau token.
- Tes regresi `scripts/test_rf30_pi_result_bridge.py`
  diperluas untuk memverifikasi toleransi noise
  sebelum start serta penolakan setelah start;
  hasil PASS. Tes firmware result gate juga PASS.

Versi yang diperbaiki disalin ke **folder terpisah** pada Pi:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/live_rf500_01/rf30_pi_result_bridge.py`.
File bridge asli di direktori staging Pi tidak ditimpa.
SHA-256 skrip lokal dan skrip di Pi sama:
`799a506c08f057667e81e9e40ae51a6b6059b435907482341945d299ab4acc71`.

## 4. Aktivasi listener terawasi

Listener dijalankan dengan:

- Port USB: `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0`
- Model: `final_model.joblib`, metadata `final_model_info.json`
- Venv: `~/smart-coffee-stage7/rf30_staging/.venv`
- Mode: `--serial-live`, dengan gate bench eksperimen yang ada
  pada script dan tanpa perintah penggerak aktuator.
- Batas waktu: `--max-seconds 1260` (21 menit sejak listener dimulai).
  Program akan berakhir jika jendela terlewati,
  dan tidak dijadikan daemon permanen.

Saat verifikasi sekitar 19:39 WIB:

```text
PID 2264 — Sl (running)
fuser /dev/ttyUSB0 → 2264
listener.log → RF30_SERIAL_LISTENER_READY_SUPERVISED
vcgencmd get_throttled → throttled=0x0
```

Log live Pi:
`~/smart-coffee-stage7/rf30_staging/com4_integration_20261117/live_rf500_01/listener.log`.
Hanya proses ini yang memegang port, dengan
serial FTDI yang sesuai. Membuka port dapat
memicu reset MCU melalui DTR pada rangkaian FT232RL.

## 5. Batas verifikasi

**Sudah terbukti:** receiver RF500 live berjalan,
port dimiliki secara eksklusif, model
dan build firmware sebelumnya telah diverifikasi,
skrip noise guard telah diuji.

**Belum terbukti pada saat laporan dibuat:** operator
menekan Start AI Test kembali, 30 siklus selesai,
900 frame masuk utuh, model memprediksi sampel baru,
MCU membalas `AI_RESULT_ACK`, maupun
LCD menampilkan `pResult`.
Hal-hal ini harus dinilai berdasarkan
log aktual setelah sesi berakhir, bukan dari
status READY saja.

Kalibrasi R0 masih dilaporkan belum tersedia;
model ini menggunakan fitur ADC mentah dan
masih eksperimental. Jangan mengklaim nilai
confidence terkalibrasi atau asal kopi.
