# 12 November 2026 — Pisahkan firmware SVM30 dan siapkan RF500 kembali ke Raspberry Pi 5

**Status keseluruhan:** source backup branch **PASS**; Pi RF500 host
**PASS software/staging dan USB enumerasi terakhir**; firmware pasangan
Pi **PASS compile-only**; pergantian firmware ATmega dan hasil RF fisik
di Nextion **BELUM DILAKUKAN**.

## 1. Pemisahan Git tanpa mengganggu pekerjaan lokal

- Cabang terpisah berhasil dibuat dan dipush:
  `backup/atmega-svm30-standalone-20261112`,
  dibekukan pada commit
  `7db96db006f780a9e78dcbea3830b21a170ae6cd`.
- Cabang aktif tetap `wahyu`. Seluruh perubahan
  lokal pengguna (termasuk `platformio.ini`,
  berkas CSV, project Nextion HMI, scripts lain) dibiarkan.
- Source compile-time SVM30 tetap disimpan dalam
  riwayat Git; parameter model privat
  `private/embedded_svm30_model.h`, model,
  backup EEPROM/Flash dan image *.hex tidak
  dipublikasikan. Backup branch **bukan salinan
  publik lengkap dari bobot model privat**.
- Firmware yang **benar-benar masih terpasang di
  ATmega** pada saat laporan ini adalah SVM30
  standalone dari B6 (50.006 byte ditulis
  dan diverifikasi pada 11 November).
  Membuat branch tidak otomatis mengganti firmware fisik.

## 2. Arsitektur yang akan dipulihkan

```text
Nextion 4.3" (Serial2 9600)
       ↓ EVT:AI_START
ATmega2560 (pompa/valve + ADS1115 + 30 siklus/900 ADC)
       │ Serial0 115200 + FT232R
       ↓
Raspberry Pi 5 (RF500 scikit-learn 1.7.2)
       │ ekstraksi 3 fitur ADC absolut
       ↓ predict [dark/light/medium]
Pi → #rf30:<token>:<roast>; → ATmega → pResult.tRoast
```

ATmega tetap mengendalikan valve/pompa, bukan Pi.
Pi memerlukan seluruh frame lengkap dengan
build ID `take30-ai30-rfhost-20261110` dan
token yang cocok; setiap paket yang salah sesi,
tidak lengkap, terlambat >30s setelah selesai,
atau duplikat harus ditolak. Origin dan
confidence tetap N/A (RF500 `predict_proba`
belum dikalibrasi).

## 3. Raspberry Pi 5 — pemeriksaan langsung lewat SSH Tailscale

- SSH menggunakan host key SSH **yang sudah
  tersimpan** untuk `enose-v3@enose-pi5`:
  berhasil. Raspberry Pi 5 aarch64, Python
  3.13.5, uptime 12 November sekitar 14:59 WIB.
- Status catu Pi `vcgencmd get_throttled=0x0`,
  tetapi **tidak memverifikasi listrik PCB,
  common ground dan jalur VBUS**.
- Pada awal pemeriksaan, `/dev/ttyUSB0`
  dan FTDI belum muncul. Pada pemeriksaan
  ulang, FT232R VID:PID `0403:6001`,
  serial `A10KNJBL` muncul via
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0`
  → `/dev/ttyUSB0` dan `lsusb`.
  `fuser` tidak menemukan pemegang aktif;
  `ModemManager` dan serial getty inactive.
  Riwayat Pi mengalami disconnect/xHCI;
  enumerasi kembali **bukan bukti kestabilan
  jangka panjang setelah serial-open**.
- Tidak ada akses ke `/dev/ttyUSB0`,
  DTR/RTS, reset, perintah MCU, pengendalian
  aktuator, atau flashing pada pemeriksaan ini.
- `avrdude` / `pio` **tidak tersedia**
  sebagai command di host Pi ketika diperiksa;
  jalur programmer Pi belum terverifikasi.
  Adaptor FT232R Pi `A10KNJBL` juga **berbeda**
  dari adaptor Windows COM5 `A10KMM3SA`
  yang dulu terbukti bisa mem-flash.

## 4. RF500 asli yang sudah tersimpan di Pi

Folder eksisting (tidak dihapus/di-overwrite):
`/home/enose-v3/smart-coffee-stage7/rf30_staging/`.

- Model pengguna `final_model.joblib`
  **2.363.398 byte** SHA256
  `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
- `final_model_info.json` dan kode host lama
  `roast_rf30_pi_inference.py`,
  `roast_rf30_pi_stream_replay.py`,
  `rf30_pi_result_bridge.py` tetap tersedia.
- Virtual environment Pi terisolasi mempunyai
  scikit-learn **1.7.2**, NumPy **2.5.4**,
  joblib **1.6.0**, SciPy **1.18.1**;
  **pyserial 3.5** ditambahkan **hanya ke venv**
  dengan pip; tidak membuka USB serial.
- Skrip readiness baru
  `pi_rf30_pi5_readiness.py` dipindahkan
  dengan SCP ke staging Pi setelah memastikan
  target belum ada. SHA lokal dan Pi cocok:
  `88195b76bd768e1286c6e68d8a8897d0aefa6bdd15a8fc77119a8c8bcff9d2a4`.
  Output `HOST_STAGED_NOT_MCU_VERIFIED`:
  seluruh dependency/port by-id terdeteksi,
  namun `live_activation_allowed=false`
  karena belum dibuktikan firmware MCU RF.
- `pi_rf30_stage_selfcheck.py`: PASS di Pi.
- `pi_rf30_stage_model_verify.py`: PASS di Pi
  tanpa deserialisasi model.
- `pi_rf30_stage_e2e_replay.py`: PASS di Pi
  menggunakan **RF asli** pada
  `D-CAT_B70.csv`, 900 ADC dan simulasi
  handshake `#rf30:B1F503A9:dark;`
  beserta ACK mock. Ini **bukan transmisi USB fisik**.
- RF500 yang ada memakai tepat 3 fitur:
  `tgs822_max_mean`,
  `tgs822_purging_mean_mean`,
  `mq8_max_mean`, dari **ADC absolut**
  (tanpa baseline correction atau z-score).
  Validasi independen yang mencakup spesimen/
  perangkat berbeda dan kalibrasi probabilitas
  **belum dipastikan**.

## 5. Paket firmware pasangan RF30 disiapkan di Windows

- Profil khusus yang sudah ada:
  `scripts/platformio_rf30_bench.ini`,
  `-DENABLE_PI_RF30_RETURN=1`,
  **tanpa** flag SVM30 standalone.
- `pio run -c scripts/platformio_rf30_bench.ini
  -e rf30_return_bench`: **PASS**,
  **35.748 byte Flash** dari 253.952 byte
  aplikasi dan **3.917 byte SRAM global**
  dari 8.192 byte.
- ELF berisi build ID
  `take30-ai30-rfhost-20261110`,
  pesan `AI_AWAITING_RESULT` dan
  `AI_RESULT_ACK`; marker standalone
  SVM30 tidak ada.
- Skrip `prepare_rf30_pi_restore_image.py`
  menolak Intel HEX yang melanggar checksum,
  out-of-bounds bootloader, tanpa EOF,
  atau duplikat alamat; tes negatif lulus.
- Paket privat:
  `private/rf30_pi_restore_image/20261112/`
  dengan `rf30_pi_return_candidate.hex`
  dan `image_manifest.json`.
  SHA256 HEX:
  `13b764d4f8b4aad3c09413bdc7a18094c1e90bf18be83dec5b6b2cb103e92440`.
  Byte Flash aplikasi: **35.748**, alamat
  **0–35.747** (tidak menulis bootloader).
- Firmware SVM30 yang sebelumnya terverifikasi
  tetap ada sebagai kandidat rollback, SHA256
  `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`,
  ditambah backup firmware/EEPROM B6.

## 6. Kenapa belum live

**Tidak boleh mengklaim Pi RF sudah aktif di LCD.**
ATmega fisik **masih SVM30 standalone**, tidak
mengeluarkan stream RF 900 ADC atau menerima
paket `#rf30:...` dari Pi; pemeriksaan USB
pasif tidak dapat mengubah hal tersebut.

Sebelum beralih fisik:

1. Konfirmasi operator bahwa alat benar-benar
   **IDLE**, tidak ada run yang berjalan,
   suplai PCB/VBUS/ground dan aktuator aman.
2. Pilih jalur bootloader/programmer yang sudah
   terbukti bekerja; jalur Windows COM5
   `A10KMM3SA` pernah diverifikasi dan dapat
   dijadikan acuan, sedangkan FTDI Pi berbeda
   dan riwayat Pi USB pernah gagal.
3. Verifikasi backup EEPROM/Flash dan image
   rollback, serta persetujuan spesifik untuk
   **mengganti firmware SVM30 dengan RF30**.
   Bootloader `wiring` berpotensi mereset MCU.
4. Flash satu kali image RF30 ke ATmega dengan
   verifikasi baca-balik. Jangan mengubah
   `platformio.ini` lokal, EEPROM atau Nextion TFT.
5. Pastikan `pHome` dan valve/pompa normal;
   kemudian jalankan listener Pi RF hanya dalam
   sesi uji **diotorisasi dengan dua opt-in**
   yang diwajibkan oleh
   `rf30_pi_result_bridge.py`.
   Jangan autostart listener secara diam-diam.
6. Tes **30 siklus/900 sampel** di Nextion.
   Konfirmasi paket RF dan **ACK MCU nyata**
   serta tampilan `pResult.tRoast`.
   Jika model, USB, timing atau 900 frame
   gagal, hasil harus **N/A**. Jangan pakai
   probabilitas RF mentah sebagai confidence
   terkalibrasi atau origin classifier.

## 7. Keputusan

**Software Pi RF500 + model + host protocol: PASS
pada replay offline real model.**
**Raspberry Pi FT232R enumeration: PASS pada
pemeriksaan terakhir; stabilitas live masih
perlu dibuktikan.**
**RF30 firmware: PASS compile-only.**
**MCU RF flash dan integrasi USB/Nextion fisik:
PENDING sampai SOP dan jalur pemrograman aman.**
**Akurasi prospektif RF pada kopi baru: BELUM
TERVALIDASI.**
