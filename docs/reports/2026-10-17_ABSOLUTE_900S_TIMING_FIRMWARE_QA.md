# Audit timing 30 siklus Smart Coffee E-Nose v2: 900 s tanpa menunggu Nextion

**Tanggal:** 17 Oktober 2026. **Status:** perbaikan firmware/receiver, simulasi host, regresi CSV, serta build ATmega2560 PASS. **Belum flash firmware timing baru dan belum uji prospektif fisik 30 siklus** pada laporan ini.

## Temuan pada data fisik B42 sebelumnya

- Sumber read-only: `data/raw/D-GAW_B42.csv`, SHA256 `536589f91f933c13bbf2769444ae80702899213d19663f0c76b3869b7875bd62`, 956 sampel, 30/30 siklus, tidak ada nilai ADC yang kosong. Rentang timestamp: **955.000 ms**, dibanding target nominal 900.000 ms.
- Masing-masing purging mempunyai 26 sampel, collecting 5–6 sampel. Rata-rata jarak awal purging antarsiklus **31.862 ms**. Durasi pengamatan bertambah sekitar 55 detik karena pergantian fase sebelumnya **ditentukan oleh callback ADC 1 Hz**, kemudian `acqPhaseStartMs=millis()` dipanggil ulang. Lateness fase tidak dipertahankan dan terakumulasi sebanyak 60 batas fase.
- Tidak ada perubahan, penulisan ulang, pemotongan, atau normalisasi retrospektif pada CSV B42. Durasi lama tetap tercatat apa adanya sebagai data historis.

## Perubahan firmware (`src/main.cpp` dan `src/acquisition_timing.h`)

1. `loop()` memeriksa jadwal batas fase sebelum dan sesudah `scheduler.execute()`, **independen dari callback ADS 1 Hz**. Batas fase dihitung sebagai `acqPhaseStartMs + durasi_fase`, lalu `acqPhaseStartMs` berikutnya mengikuti **deadline lama**, bukan waktu selesainya `sensors.readAll()` atau `NextionTransport`.
2. Tetap 30 × (25 s purging + 5 s collecting) = **900.000 ms waktu aktif** untuk Take Data. AI Test tetap 5 siklus. Pause membekukan waktu aktif; setelah resume, deadline bergeser sesuai durasi pause. Helper deadline memakai signed distance wrap-safe terhadap overflow `millis()`.
3. **Tidak membangkitkan sampel buatan, tidak mengubah ADC ataupun frekuensi scheduler ADS 1 Hz.** Fitur inferensi yang sebelumnya terakumulasi pada callback ADC sekarang diakumulasi di callback ADC saat collecting, bukan pada peristiwa pergantian fase. Format JSON sampel dan kolom CSV **tetap sama**.
4. `NextionTransport::tryText/tryProgress` memastikan perintah status **hanya dikirim jika seluruh frame muat dalam buffer TX UART**. Perintah yang tidak muat dilewatkan tanpa blocking. Tampilan pDataRun dijadwalkan satu perintah per 125 ms: `tSample`, `tCycle`, `jCycle`, `tPhase`, `tRemain`, `tTemp`, `tHum`, `tSensors`; setiap komponen diperbarui kira-kira sekali/detik selama kapasitas buffer mencukupi. Fungsi navigasi halaman existing (`showNextionPage`) masih memakai delay singkat saat perpindahan halaman; **tidak dipanggil tiap siklus sampling**.
5. Jika pemeriksaan deadline terlambat **>=1.000 ms** (setidaknya satu interval ADC), firmware mengirim `ACQ_TIMING_FAULT` kemudian `ACQ_STOP`, mematikan aktuator dan menunjukkan alert; receiver mempertahankan dataset menjadi *incomplete*, **tidak mempublikasikannya sebagai run valid**. Jangan memperpendek fase diam-diam untuk mengejar jadwal.
6. Event `ACQ_COMPLETE` menambahkan `elapsed_active_ms`, `target_active_ms`, `paused_ms` di luar data sensor/CSV. Receiver versi baru memverifikasi durasi aktif **dalam ±1.000 ms** dari 900.000 ms untuk protokol baru. Firmware lama tanpa tiga field itu tetap didukung; ketidaksesuaian laporan firmware baru menyebabkan *incomplete*. Log menerima ringkasan timing PASS/FAIL; jika sensor sample ditolak, log menyimpan nama field dan metadata agar diagnosa lebih informatif, tidak menyalin 10 nilai ADC ke pesan error.
7. Tetap Serial2/Nextion @9600, USB @115200, Calibrate = 60 sampel ADC dan **tidak menulis ulang EEPROM R0**, AI hasil N/A, firmware 12 halaman pTake/pDataRun/pDataDone tidak berubah.

## QA host dan build

- `python scripts/test_absolute_timing_firmware.py`: **PASS**. Tes C++ native menggunakan **helper `src/acquisition_timing.h` yang sama dengan firmware AVR**; simulasi 30 siklus pada jitter loop 1,11,80,250 ms memberi elapsed **900.000, 900.009, 900.044, 900.044 ms**, 60 transisi, peluang pengambilan ADC 1 Hz **750 purging + 150 collecting**. AI 5 siklus, overflow 32-bit, pause +7,5s, dan stall 1.250ms (fault) PASS.
- `python scripts/test_acquisition_integrity.py`: **PASS** untuk 30×25+5 sampel, timing baru 900.070ms diterima, 955.000ms ditolak dan dikarantina, event `ACQ_TIMING_FAULT` dikarantina. Data historis/CSV asli tidak berubah.
- `python scripts/test_12_page_take_data_contract.py`, `scripts/test_take30_contract.py`, `scripts/test_baseline_firmware_contract.py`, `scripts/test_baseline_recording.py`, `scripts/test_usb_autodetect.py`: PASS. HMI dapat dikunci oleh Nextion Editor; test membaca snapshot Git 12 halaman dalam kondisi tersebut tanpa memaksa Editor ditutup.
- `pio run -e mega2560`: **SUCCESS**. Build ID baru: `take12-abs900-no-uiwait-20261017`.

## Batas dan temuan terpisah

- Simulasi 900 detik menguji kalkulasi deadline, **bukan bukti aktuator mencapai ±0ms pada perangkat fisik**. Hasil fisik perlu dikonfirmasi dari `ACQ_COMPLETE.elapsed_active_ms` dan validasi CSV setelah update firmware.
- Log receiver mencatat run baru B42 mulai **18:39:05**, kemudian **incomplete pukul 18:40:03** karena payload dengan `phase` kosong (`invalid phase: ''`). Ini adalah **temuan kualitas data terpisah**: belum ada bukti penyebab; source firmware selalu mengirim `acqStateName()` yang bernilai purging/collecting untuk sampel. Jangan menyatakan ini telah disembuhkan hanya oleh perbaikan timing. Logging diagnostik ditambah untuk run berikutnya.
- Walaupun sesi receiver sudah incomplete, **itu tidak menjamin ATmega/aktuator berhenti**. Tidak ada perintah serial, flash, restart listener, atau penghentian fisik dalam audit ini; demi keselamatan, tunggu konfirmasi operator bahwa LCD dan aktuator sedang **IDLE**, lalu lakukan flashing dan restart receiver terawasi. Setelah itu jalankan Take Data penuh tanpa Pause untuk menguji 900 detik dan kualitas ADC.
