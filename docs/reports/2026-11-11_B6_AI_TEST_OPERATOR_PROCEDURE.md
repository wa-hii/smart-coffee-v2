# B6 — Protokol uji akhir Embedded SVM30 tanpa Raspberry Pi

**Tanggal:** 11 November 2026 (WIB). **Status:** firmware SVM30 telah
di-flash dan diverifikasi oleh avrdude; operator menyatakan setelah
flashing LCD Nextion normal di pHome, pompa/dinamo normal, dan valve
solenoid diam dalam IDLE. **Hasil run AI fisik belum dilaporkan**.

## Tujuan

Menguji *secara fisik* seluruh alur independen Raspberry Pi:

```
10-channel ADC → 30 siklus (purge 25s, collect 5s)
→ 900 sample 1 Hz → 30 fitur streaming
→ SVC RBF 125 support vector pada ATmega2560
→ Nextion pResult.tRoast = LIGHT / MEDIUM / DARK
```

Raspberry Pi, listener COM5, CSV, koneksi jaringan, serta penyimpanan
historis **tidak diperlukan**. Halaman hasil memberi Origin dan
Confidence `N/A` karena belum ada model origin/probabilitas terkalibrasi.

## Alat dan kondisi sebelum START AI TEST

- Gunakan kopi dengan roast yang **diketahui independen**
  (LIGHT / MEDIUM / DARK); catat label sebenarnya **di luar model**.
- Pastikan sensor sudah mencapai pemanasan/kondisi stabil
  sesuai SOP alat dan sampel kopi terpasang seperti prosedur biasa.
- Nextion berada pada `pHome`, pompa/dinamo hidup normal,
  solenoid valve diam saat IDLE, tidak ada bau panas/
  kebocoran/tegangan abnormal.
- Jika perlu membedakan perangkat, gunakan halaman Settings:
  source profil standalone menetapkan `tFw = SVM30-LOCAL`
  dan `pTest` mencantumkan `SVM30 BENCH`.
  Ini bukan bukti otomatis bahwa operator sudah melihatnya.
- **Jangan membuka COM5 di Serial Monitor**: driver FT232 dapat
  memicu DTR reset. Jangan menjalankan receiver
  `lcd_acquisition_service.py` atau script lain yang
  mengirim `#start`/commands. Firmware standalone memang
  menonaktifkan remote START pada Serial0.
- **Jangan mengubah firmware, EEPROM, HMI/TFT atau kalibrasi**
  ketika menjalankan B6. Ambil foto layar bila dibutuhkan,
  bukan CSV sensor.

## Cara menjalankan satu run fisik

1. Dari `pHome`, buka menu **AI Test** (`pTest`).
   Pastikan tidak ada alert `ADC ERROR`; jika ada,
   jangan mulai dan dokumentasikan.
2. Tekan **START AI TEST** **satu kali** di Nextion.
   Firmware seharusnya menampilkan `pTestRun`
   serta indikator `LOCAL MCU` dan sisa waktu sekitar 15:00.
3. Per siklus: **25 detik purging** (valve solenoid OFF)
   dan **5 detik collecting** (valve ON).
   Pompa bekerja sesuai desain perangkat.
   Ulangi **30 kali**, total nominal **900 detik**.
4. Awasi setidaknya siklus 1, perpindahan awal
   purging→collecting→purging, siklus tengah, dan
   siklus 30. Jaga perangkat di bawah supervisi operator.
5. Bila ada bau panas, relay/valve macet, gerakan
   aktuator di luar fase, reset LCD berulang,
   `Timing error`/`AI Test invalid`, atau
   keadaan berbahaya, tekan **CANCEL** atau
   lakukan prosedur aman sesuai SOP. **Jangan
   restart/flash/ulang siklus otomatis**.
6. Pada fase collecting terakhir, valve harus
   kembali OFF sebelum MCU menyelesaikan prediksi.
   Setelah inferensi lokal, Nextion seharusnya
   membuka `pResult` dan menunjukkan
   `LIGHT`, `MEDIUM`, atau `DARK`
   di komponen `tRoast`. `tOrigin`,
   `tRConf`, dan `tOConf` boleh
   `N/A`; bukan error sistem untuk profil ini.
7. Bandingkan prediksi dengan roasting sebenarnya,
   catat status LED/pompa/valve ketika kembali IDLE.
   Jika pResult = `N/A`, jangan melabeli sebagai
   benar; itu *abstain/fail closed* dan memerlukan
   investigasi kelengkapan sensor, SRAM, timing
   maupun komunikasi Nextion.

## Kriteria penerimaan B6

**PASS fungsional end-to-end** jika semuanya terbukti:

- `pHome → pTest → pTestRun → pResult` tanpa macet;
- sensor secara fisik berfungsi dan **30×(25s+5s)**
  berjalan tanpa `Timing error` atau `AI Test invalid`;
- valve sesuai fase dan kembali OFF di IDLE;
- hasil `tRoast` **LIGHT/MEDIUM/DARK** (bukan N/A)
  tampil **tanpa Raspberry Pi**;
- prediksi dengan label kopi yang diketahui direkam
  sebagai **uji satu sampel**, bukan klaim tingkat
  akurasi keseluruhan.

**B5 runtime** tetap membutuhkan pengukuran
stack watermark dan waktu inferensi pada AVR
16 MHz untuk release produksi. Lolos satu kali
AI Test tidak menggantikan uji berulang/prospektif
lintas roast, origin, dan perangkat.

## Format hasil yang harus dilaporkan operator

| Parameter | Isi oleh operator setelah selesai |
|---|---|
| Kopi dan roast sebenarnya | ... |
| Tampilan awal `pTest` | SVM30 BENCH / lainnya |
| Tombol START dan `pTestRun` | muncul / tidak |
| Fase purge/collect dan siklus | normal 30 siklus / masalah |
| Valve kembali OFF | ya / tidak |
| Durasi aktual (perkiraan) | ... menit |
| Tampilan akhir | pResult / pAlert / macet |
| `tRoast` terbaca | LIGHT / MEDIUM / DARK / N/A / lainnya |
| Hasil vs roast sebenarnya | sesuai / berbeda / tidak dapat dievaluasi |
| Foto dokumentasi | opsional |

**Penting:** Keberhasilan B1–B3 **199/199** adalah
*equivalence* prediksi C++ terhadap Python
pada corpus replay, **bukan 100% klasifikasi
benar**. Dalam corpus replay berlabel yang sama,
156/199 prediksi sesuai label sebenarnya (78,4%),
dan corpus tersebut **bukan validasi prospektif
independen**. Karena itu tidak boleh mengklaim
akurasi fisik sampai eksperimen lapangan terukur.

## Bukti teknis dan pengaman

- Firmware terpasang diverifikasi avrdude:
  **50006 bytes written + 50006 bytes verified**,
  signature ATmega2560 `0x1e9801`,
  SHA256 kandidat
  `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`.
- Backup EEPROM dan Flash lama tetap privat;
  rollback app-only telah disiapkan tetapi
  **belum pernah diuji pemulihan fisik**.
- Host tidak memiliki cara aman untuk menekan
  Nextion secara langsung pada build standalone;
  **START AI TEST harus diaktifkan operator
  melalui LCD**, bukan dengan USB serial.
- Status laporan ini **PENDING PHYSICAL TEST** hingga
  operator benar-benar mengirim hasil run.
