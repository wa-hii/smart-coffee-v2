# B4–B6: Firmware standalone SVM30 ATmega2560 dan kesiapan uji perangkat

**Tanggal:** 11 November 2026, WIB. **Branch:** `wahyu`.

**Ringkasan status:**

- **B4: PASS untuk integrasi firmware source + AVR compile-only**.
- **B5: PASS untuk QA offline/memori statis; PARTIAL untuk
  stack maksimum dan waktu inferensi fisik**.
- **B6: BLOCKED (NO-GO untuk flash/uji perangkat fisik)**,
  karena Nextion terakhir dilaporkan stuck `Initializing Systems`,
  dan FT232R/USB Pi belum pulih. Tidak ada izin SOP spesifik
  untuk flashing ISP/USB yang aman dan backup image hardware belum dibuat.
- **Tidak ada flashing, perintah serial, reset USB/Pi, perubahan
  HMI/TFT, kalibrasi EEPROM, atau aktuator** selama tahap ini.

## 1. Tujuan dan kompatibilitas

Mode cadangan yang diminta: `Sensor ADS1115 → ATmega2560 (30 siklus
× 25 detik purging + 5 detik collecting) → akumulator streaming
30 fitur → SVM RBF 125 support vector → Nextion pResult`.

Tidak memerlukan Raspberry Pi, host UART, penyimpanan 900 baris
CSV, database, atau jaringan. Model asli `final_svm.joblib`
(SHA256 `d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33`)
tidak ditraining ulang. Header parameter SVM disimpan
di `private/embedded_svm30_model.h`, **tidak di-Git**.

Source firmware utama diubah secara **compile-time gated**;
default `platformio.ini` beserta pengaturan COM lokal pengguna
tidak diubah. Perintah membangun firmware cadangan:

```text
pio run -c scripts/platformio_svm30_standalone.ini -e svm30_standalone
```

**Jangan menjalankan `-t upload` pada perangkat bermasalah.**

## 2. B4 — integrasi software (PASS)

Pada `src/main.cpp`, hanya jika dua flag build
`SMART_COFFEE_STANDALONE_SVM30=1` dan
`ENABLE_AVR_SVM30=1` aktif:

1. `startAcquisition(AI_TEST)` mereset akumulator model,
   prediksi dan counter, lalu mempertahankan valve purging normal.
2. `adsCallback()` membaca ADC sebanyak 1 Hz; setiap sampel
   lengkap (10 kanal) langsung dikirim ke fungsi
   `svm30Capture.add()`, dengan `cycle`, `phase` dan
   `sample_idx`. Sensor yang dibutuhkan: TGS822, TGS2602,
   TGS816, MQ8. Tidak ada `sensors.printJsonData` untuk AI
   standalone, tidak ada CSV dan tidak ada buffer 900 sampel.
3. Jika ADC tidak tersedia atau fase/urutan rusak, akuisisi
   dihentikan dan solenoid OFF; Nextion mendapat
   `pAlert`. Tidak ada prediksi dari sesi tidak lengkap.
4. Setelah collecting terakhir, **valve OFF lebih dahulu**,
   baru `doInference()`. Inference mewajibkan **900
   sampel** + `svm30Capture.complete()` + fitur valid +
   precheck SRAM bebas minimal **2048 byte**.
5. SVM RBF mengembalikan `dark/light/medium`,
   ditranslasikan ke `AiRf30Return::Roast` dan
   ditampilkan di komponen Nextion `pResult.tRoast`
   sebagai `DARK/LIGHT/MEDIUM`. Pada gagal, `N/A`.
   `tRConf`, `tOrigin`, `tOConf` tetap `N/A`,
   progress probability tetap nol karena tidak ada
   model origin atau confidence SVM terkalibrasi.
6. `EVT:AI_CANCEL`, `stopAcquisition()`, sesi baru
   membatalkan hasil lama. Tombol Take Data dinonaktifkan,
   event `EVT:DATA_START`, `EVT:CAL_START` dan
   `EVT:RESULT_SAVE` menampilkan informasi
   bahwa perekaman/penyimpanan tidak tersedia.
   `Serial.available()` parser dimatikan pada
   profil ini sehingga tanpa Pi tidak ada remote START.
   Desain visual HMI tidak diubah.
7. Startup bench standalone menghindari pemindaian penuh
   126 alamat I²C dan mengaktifkan
   `Wire.setWireTimeout(25000,true)`, supaya transaksi
   I²C yang gagal tidak menggantung firmware tanpa batas.
   Efek ini **belum diuji pada sensor fisik**.

Build ID berbeda untuk profil ini:
`standalone-svm30-bench-20261111`.
Build default tetap memiliki identitas
`take30-ai30-rfhost-20261110`.

### Bukti B4

- `python scripts/test_svm30_standalone_contract.py`: PASS.
- `python scripts/test_30cycle_take_ai_sync.py`: PASS
  (kontrak default Pi 30 siklus tetap identik).
- `python scripts/test_rf30_firmware_result_contract.py`: PASS.
- `python scripts/test_stage1_firmware_contract.py`: PASS.
- Verifier kontrak 12 halaman Nextion/23 event: PASS,
  tetap Serial2 9600 baud dan tanpa modifikasi aset.
- `avr-strings` pada hasil standalone mengonfirmasi
  `ACQ_START`, `ACQ_COMPLETE`, `PHASE_CHANGE`
  dan `RESULT_EXPORT` **tidak ada** pada executable
  standalone; string `LOCAL MCU`,
  `MODE DATA TIDAK TERSEDIA`, `SVM30 BENCH`
  **ada**. Ini memverifikasi tidak ada output streaming
  CSV/USB dari jalur AI standalone yang dikompilasi.

## 3. B5 — hasil kompilasi dan batas QA

| Build | Flash | SRAM global | Status |
|---|---:|---:|---|
| Firmware default `mega2560` | 34.760 B | 3.899 B | PASS, unchanged |
| **Standalone penuh `svm30_standalone`** | **50.006 B** | **4.189 B** | **PASS compile-only** |
| Diagnostik tanpa LTO `svm30_stack_diagnostic` | 54.302 B | 4.206 B | PASS diagnostic compile-only |

ATmega2560 memiliki 8.192 byte SRAM; pada build standalone
terpakai 4.189 byte *global/static*. Sisanya **4.003 byte
untuk stack, heap, interrupt dan runtime**; angka itu bukan
pengukuran stack aktual.

Diagnostik dengan compiler `-fstack-usage` tanpa LTO
memberikan perkiraan *frame* fungsi:

- `EmbeddedSvm30::Classifier::predict`: **663 byte**.
- `doInference`: **127 byte**.
- `processAcquisitionState`: **160 byte**.
- `adsCallback`: **41 byte**.
- `EmbeddedSvm30::Features::add`: **44 byte**.

Ini adalah *frame* per fungsi hasil analisis compiler,
**bukan total stack puncak**, dan belum menghitung kedalaman
penelusuran fungsi `expf`, interrupt, serta situasi hardware.
Pengaman `standaloneFreeRam() >= 2048` sebelum inferensi
ditambahkan untuk menolak run yang kekurangan RAM. B5
**belum lulus** sub-gate pengukuran stack watermark dan
latensi inferensi pada ATmega 16 MHz secara fisik.

Model 125 SV (15.000 byte) dan dual coeff (1.000 byte)
terverifikasi berada pada section Flash (PROGMEM)
melalui `avr-nm`, bukan SRAM.

Pengujian terhadap 199 CSV valid memakai kode B1–B3:
**199/199 prediksi sama dengan sklearn 1.7.2**;
selisih terbesar skor pasangan SVM **3,6055e-6**.
**10 sesi rusak** ditolak native test.
Ini membuktikan *parity* model pada corpus teruji, **bukan
pengujian papan fisik/latensi/akurasi kopi baru**.

### Artefak lokal privat (tidak untuk GitHub)

- `private/svm30_standalone_firmware.hex`:
  firmware **kandidat, bukan release approved**.
- SHA256 HEX:
  `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`
  (140.676 bytes representasi Intel HEX).
- `private/svm30_standalone_firmware_manifest.json`
  menyimpan hash/model/profil dan status **NOT FLASHED**.
- File header PROGMEM lengkap dari model pengguna dan
  golden references juga `private/`, diabaikan Git.

## 4. B6 — kondisi perangkat dan keputusan GO/NO-GO

**Hasil SSH read-only langsung ke Pi pada 11 November 2026
pukul 15:41:08 WIB:**

- Raspberry Pi 5 masih menyala dan dapat diakses.
- `vcgencmd get_throttled = 0x0`.
- `lsusb` hanya menemukan root hubs; **FT232R tidak ada**.
- `/dev/ttyUSB*` dan `/dev/serial/by-id` **tidak tersedia**.
- Log kernel tetap mencatat `xHCI host controller not responding`,
  `HC died; cleaning up` dan FT232R disconnect pada
  pukul 11:59:29 WIB, setelah G2 serial-open gagal.
- Operator sebelumnya melaporkan LCD Nextion stuck
  `Initializing Systems`, meskipun PCB dan LCD berdaya;
  pompa/dinamo berjalan sesuai mode alat, valve diam pada idle.
- **Tidak ada bukti baru** bahwa boot `pSplash → pHome`
  atau komunikasi Nextion Serial2 pada hardware telah pulih.

Oleh karena itu **B6 = BLOCKED / NO-GO**, bukan FAIL
inferensi SVM, dan bukan izin flashing melalui remote.
Jangan menghubungkan komputer/programmer langsung saat
hardware masih dalam kondisi ini tanpa SOP dan pemeriksaan
jalur PSU/ground/VBUS/FT232.

### Langkah G0/B6 terawasi yang belum dilakukan

1. Operator dan hardprog memeriksa suplai PCB/Nextion/USB,
   isolasi daya, common ground dan potensi backfeed;
   mendokumentasikan kondisi pompa/valve, wiring dan
   startup saat kabel Pi **dipisah hanya ketika aman**.
2. Setelah B0 **PASS** (LCD dapat tampil `pHome`
   stabil tanpa Pi), pilih jalur flashing **ISP atau
   USB langsung yang benar-benar tervalidasi**, catat identitas
   perangkat serta backup firmware dan EEPROM terlebih dahulu.
3. Validasi checksum file `.hex` dan layout Flash.
   Jangan hapus EEPROM R0 atau mengganti visual Nextion/TFT.
4. Flash kandidat hanya dengan izin SOP spesifik dan
   operator standby dengan langkah pemulihan.
5. Uji cold boot → halaman pHome, tombol `AI TEST`,
   run 30 × (25+5) sekali, valve fail-safe,
   dan hasil pada `pResult` setelah sensor valid.
6. Ukur runtime stack watermark, lama klasifikasi,
   ketepatan 900 sampel, latency Nextion,
   temperatur/daya selama 15 menit dan cancel/error.
7. Lakukan blind test pada kopi fisik baru untuk
   Light/Medium/Dark dan unknown. Jangan mengklaim
   akurasi produksi hanya dari CV metadata.

**Kesimpulan:** jalur program standalone benar-benar telah
diintegrasikan dan bisa dibangun untuk MCU, tetapi
**alat fisik belum dikonfirmasi berjalan end-to-end**.
