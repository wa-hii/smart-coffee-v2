# Audit kalibrasi R0 dan baseline ADC melalui LCD Nextion

**Status:** implementasi kode dan pengujian offline; firmware belum di-flash pada PCB dalam pekerjaan ini dan belum ada file baseline fisik baru. HMI Nextion yang sudah terpasang memakai event EVT:CAL_START; tidak memerlukan perubahan biner HMI.

## Temuan dan perbaikan R0

Library MQUnifiedsensor dan TGSSensor sudah menghasilkan satu estimasi R0 per pengukuran ADC melalui fungsi calibrate(). Firmware lama menjumlahkan sepuluh hasil, kemudian membagi dengan RL, bukan dengan jumlah pembacaan. Pembacaan R0 dari EEPROM juga dibagi RL sekali lagi. Kedua langkah telah dikoreksi: R0 = jumlah 10 estimasi / 10; load R0 secara langsung tanpa membagi RL.

Fungsi kalibrasi R0 sekarang menolak ADS tidak lengkap atau kandidat tidak finite/<=0, dan hanya mengizinkan penulisan EEPROM setelah semua sepuluh nilai lolos. EEPROM signature versi lama 0xA5 tidak otomatis ditafsirkan dalam format baru: versi dikoreksi memakai 0xA6. **Isi EEPROM lama tidak dihapus atau ditimpa oleh tombol Calibrate.** Jika firmware ini di-flash, data R0 legacy tidak dipakai kembali tanpa kalibrasi eksplisit yang terawasi. R0 belum diperlukan untuk merekam ADC mentah; AI tetap dinonaktifkan / N/A. Jalur tulis R0 tetap hanya untuk build dengan flag IS_CALIBRATING_GAS_SENSOR=1 (default 0).

## Prosedur baseline v1

1. Pastikan ruang sensor dalam udara bersih terkontrol, warm-up memadai, alat IDLE, dan listener PC terhubung. Dari Nextion buka Calibrate, tekan Start Calibration.
2. Firmware mengatur valve posisi PURGING dan memulai perekaman baseline 60 sampel @1 Hz. HMI menampilkan REC n/60, lalu CAPTURE DONE. Tidak ada penulisan R0 ke EEPROM dari tombol ini.
3. Firmware mengirim BASELINE_START (protokol clean_air_adc.v1, build ID, total 60, tanpa tulis EEPROM), diikuti 60 BASELINE_SAMPLE berisi sample_idx, timestamp millis sejak boot, 10 ADC, suhu dan RH. Setelah itu BASELINE_COMPLETE.
4. Listener menyimpan file khusus di data/baseline/BASELINE_YYYYMMDD_HHMMSS_<id>.csv, tidak dicampur dengan data kopi di data/raw/. Hanya publish setelah urutan indeks 1..60, interval 900..1100 ms, ADC valid dan suhu/RH plausibel; jika terputus, pembacaan tidak lengkap/parsial, atau dibatalkan, file disimpan di data/baseline/incomplete/. Tidak menimpa file lama.
5. Listener membuat file QC JSON bernama BASELINE_...baseline_qc.json berisi B0 tiap sensor = median ADC 10 sampel terakhir, drift berdasarkan median 10 pertama vs 10 terakhir, rentang suhu/RH, dan SHA-256. Drift >1% ditandai perlu review sebagai ambang eksploratif, bukan pembuktian kadar udara bersih atau kelayakan model AI.
6. Selama baseline aktif tombol Take Data/AI Test dinonaktifkan oleh firmware. HOME atau perintah #stop; akan membatalkan sesi. Indikator CAPTURE DONE menandakan firmware menyelesaikan stream, bukan konfirmasi host telah menyimpan CSV; bukti penyimpanan dicek dari CSV/QC dan log.

## Batas interpretasi

Untuk D-GAW_B41 yang sudah diambil sebelum baseline baru, baseline kemudian **tidak boleh dianggap referensi pra-B41 secara retrospektif**. Untuk sampel selanjutnya, catat identitas specimen/batch dan pasangan file baseline secara terpisah. Sebuah baseline hanya layak dijadikan acuan B0 jika operator mengonfirmasi kondisi udara bersih dan stabilitas sensor. Kalibrasi ppm dan identifikasi roast/origin fisik belum dibuktikan.

## Pengujian sebelum deployment

- Build PlatformIO mega2560: SUCCESS.
- scripts/test_baseline_recording.py: mencakup sukses 60 sampel dan QC, kegagalan 59 sampel, frame invalid, event abort, kontrak EEPROM fail-closed.
- scripts/test_baseline_firmware_contract.py: memeriksa event Nextion existing, jalur tanpa EEPROM write, koreksi matematis R0, signature EEPROM dan AI disabled.
- scripts/test_acquisition_integrity.py, scripts/test_take30_contract.py, scripts/test_acquisition_payload.py: kompatibilitas CSV kopi dan kontrak Take Data 30 siklus.

Untuk penggunaan fisik, diperlukan flashing terawasi saat COM5 dan alat IDLE, menjalankan listener versi baru, uji capture 60 sampel di udara bersih, verifikasi CSV+JSON, tanpa menjalankan R0 EEPROM re-calibration.
