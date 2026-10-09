# Kontrak sistem dan keputusan rekayasa — Tahap 0

**Tanggal audit:** 9 Oktober 2026. **Ruang lingkup:** baseline kode/dokumen secara offline; bukan sertifikasi wiring/alat fisik. Dokumen ini melengkapi `00_CURRENT_STATE.md` dan menjadi acuan lintas subsistem untuk Tahap 1–10.

## 1. Status bukti dan sumber acuan

| Lapisan | Sumber implementasi atau data | Status bukti |
|---|---|---|
| Firmware MCU, fase, event, baud dan mode | `src/main.cpp`, `src/sensor.*`, `src/actuator.*`, `src/inference.*` | Diperiksa terhadap kode; build offline, **bukan** pengukuran fisik |
| Peta ADC dan urutan sensor | `src/sensor.h`, `src/sensor.cpp`, `scripts/acquisition_schema.py` | Konsistensi statis diperiksa; koneksi PCB belum diverifikasi |
| Nextion | HMI `nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI`, `src/nextion_transport.*` | Pemeriksaan HMI offline; kompilasi/editor dan TFT aktual belum dibuktikan |
| Akuisisi dan autosave | `scripts/acquisition_schema.py`, `lcd_acquisition_service.py`, `validate_acquisition.py` | Regresi dan validasi CSV offline; listener COM5 nyata tidak diuji ulang |
| Dataset | `data/raw/` B32–B35 dan `data/raw/legacy_mq9/` | 86 CSV B32+ terinventarisasi; kualitas sensor/ground truth belum dibuktikan |
| Model dan fitur | `scripts/extract_b32_features.py`, `models/`, `results/` | Fitur kandidat MQ3 tersedia; artefak RF historis MQ9 bukan model produksi |
| Host Raspberry Pi | `docs/04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md` | Rancangan; belum ada adapter Pi dan transport dua arah terverifikasi |
| Operasi hardware | Skematik aktual, SOP dan foto/perakitan yang disetujui operator | **Belum terverifikasi** pada audit offline |

Urutan keputusan apabila bertentangan: **hasil pengujian yang dapat diulang → kode dan data aktual → datasheet/pinout resmi untuk fakta hardware → dokumentasi status → rancangan roadmap**. Kesimpulan fisik wajib divalidasi terhadap PCB nyata sebelum wiring/operasi.

## 2. Kontrak yang telah dikonfirmasi secara statis

| Aspek | Kontrak aktual |
|---|---|
| Perangkat | ATmega2560; empat ADS1115 I2C pada `0x48`, `0x49`, `0x4A`, `0x4B`; SHT30 melalui `Wire` |
| Urutan ADC | `adc_tgs822`, `adc_mq135`, `adc_mq3`, `adc_tgs2611`, `adc_tgs2620`, `adc_tgs2600`, `adc_tgs2602`, `adc_mq8`, `adc_tgs813`, `adc_tgs816` |
| Akuisisi | 5 siklus; setiap siklus **purging 25 detik → collecting 5 detik**, interval task ADS nominal 1000 ms |
| Mode | `labeled_data` untuk AMBIL DATA; `ai_test` untuk START TEST |
| Nextion | `Serial2` 9600 baud; HMI acuan 12 halaman; event ASCII `EVT:*` dan terminator Nextion FF FF FF |
| Host USB yang aktif | `Serial` 115200 baud untuk data sensor/event, diagnostik dan perintah `#...`; listener komputer pasif pada port yang dikonfigurasi |
| Data sensor | JSON per baris dengan `phase`, `cycle`, `sample_idx`, `timestamp` uptime milidetik, 10 nilai `adc_*`, `temperature_c`, `humidity_rh` |
| CSV mentah | `timestamp,sample_id,roast_level,origin,batch_id,run_id,phase,sample_idx`, 10 kolom ADC sesuai urutan, `temperature,humidity` |
| Inferensi | `USE_ON_DEVICE_INFERENCE=0` secara bawaan; layar menunjukkan N/A, jalur hasil AI dari Pi belum diterapkan |

**Dua jenis waktu berbeda:** `timestamp` MCU adalah `millis()` sejak boot, **bukan** waktu kalender. Durasi 150 detik adalah nominal, bukan hasil pengukuran timing aktuator di perangkat nyata.

## 3. Koreksi pin berdasarkan sumber resmi

Datasheet resmi **Microchip ATmega2560 (TQFP-100)**, Figure 1-1:

| Sinyal | Nomor pin IC TQFP-100 | Header Arduino Mega |
|---|---:|---|
| `PH0/RXD2` (Nextion → MCU) | **12** | **D17/RX2** |
| `PH1/TXD2` (MCU → Nextion) | **13** | **D16/TX2** |
| `PD3/TXD1` (opsi UART Pi) | **46** | **D18/TX1** |
| `PD2/RXD1` (opsi UART Pi) | **45** | **D19/RX1** |

Sebelumnya ada klaim bahwa PH0/PH1 berada pada pin fisik IC 8/9. Berdasarkan datasheet, pin 8/9 justru PE6/PE7. Nomor itu **tidak digunakan lagi sebagai referensi pin kemasan TQFP-100**, tetapi belum ada perubahan kabel/perangkat. Jika desain PCB memakai penomoran lain (konektor atau modul), cocokkan nama net dengan skematik.

Referensi resmi: [Microchip ATmega2560 datasheet, Figure 1-1](https://ww1.microchip.com/downloads/en/devicedoc/atmel-2549-8-bit-avr-microcontroller-atmega640-1280-1281-2560-2561_datasheet.pdf) dan [Arduino Mega 2560 pinout](https://docs.arduino.cc/resources/pinouts/A000067-full-pinout.pdf).

**Penting untuk rencana UART Pi:** perintah diagnostik `#pin_scan;` saat ini mencakup Arduino D19/RX1 **serta D20/SDA I2C**. Perintah itu dapat mengubah konfigurasi pin dan memberi sinyal HIGH selama uji. **Jangan jalankan `#pin_scan;` ketika Raspberry Pi atau sensor I2C terhubung tanpa SOP khusus.** Pekerjaan pengamanan perintah ini masuk Tahap 1 sebelum mengaktifkan UART permanen.

## 4. Kontrak label, sesi, dan mode AI

- `sample_id` = kode pilihan kopi (misalnya `D-TEM`); `batch_id` = batch akuisisi. Keduanya **tidak** membuktikan bahwa sampel fisik independen.
- `run_id` / `cycle` = urutan pengulangan 1–5 pada satu file akuisisi.
- `session_id` unik, `physical_specimen_id`, `measured_at_utc`, versi firmware/hardware dan `message_seq` **belum ada** pada protokol produksi. Ini persyaratan metadata baru; bukan field yang boleh diasumsikan sudah tersedia.
- Preset origin tersimpan pada `scripts/3_collect_data.py` dan `scripts/lcd_acquisition_service.py`. Pemetaan untuk **30 sample_id yang beririsan konsisten**, tetapi kolektor manual memiliki tiga preset tambahan: `L-CAW`, `M-CAW`, dan `M-MUK`. Listener dapat menggunakan fallback `ORIGIN_BY_CODE` untuk kode tersebut, tetapi definisi per sampel belum eksplisit. `TEM` dan `MUK` berisiko mencampur asal geografis, produsen, dan roasting; kode `CAW` masih berupa kode tanpa definisi resmi. **Jangan otomatis menggabungkan/merelabel histori tanpa konfirmasi pemilik data.**
- **Ketidaksesuaian mode AI:** `src/main.cpp::startAcquisition(AI_TEST)` masih mencetak pilihan `sample_id`, `roast_level`, dan `origin_code` meski pada pengujian kopi tersebut belum diketahui. Listener saat ini menolak mode `ai_test` untuk dataset berlabel; namun protokol mendatang **wajib menghilangkan label jawaban pada AI_TEST**, agar tidak menyebabkan informasi menyesatkan atau kebocoran label.
- Dalam protokol target, hanya `labeled_data` yang membawa label referensi. Hasil `AI_TEST` harus berasal dari model valid, atau berstatus `unknown` / `N/A`.

## 5. Keputusan transport Raspberry Pi belum final

**Transport yang benar-benar ada:** JSON sensor/event melalui USB `Serial` 115200 ke komputer.

**Kandidat desain:** UART terpisah pada ATmega `Serial1` (TX D18/PD3, RX D19/PD2) ke GPIO UART Raspberry Pi 5 melalui **translator logika 5 V↔3,3 V yang sesuai**, dengan GND bersama; `Serial2` Nextion tetap independen. Alternatif USB serial dapat dipakai bila konfigurasi PCB dan penggunaan port memungkinkan.

`Serial1.begin(...)`, routing data, parser hasil, protokol versi 1, dan validasi perangkat **belum terimplementasi**. Keputusan akhir membutuhkan verifikasi skematik PCB, daftar pin yang telah dipakai, rangkaian translator, sumber daya, dan SOP; lanjutkan pada Tahap 7 tanpa mengubah implementasi aktif diam-diam.

## 6. Temuan terbuka dan pemilik tahap

| ID | Prioritas | Temuan atau keputusan tertunda | Lanjut pada tahap |
|---|---|---|---|
| T0-01 | **P0 keselamatan** | `#pin_scan;` berpotensi mengganggu UART1 dan SDA/I2C; wajib ditinjau sebelum bench test dengan Pi | **Tahap 1** |
| T0-02 | P0 metode | `AI_TEST` membawa label pilihan user pada `ACQ_START`; pisahkan metadata berlabel dan tidak berlabel | **Tahap 1 / 7** |
| T0-03 | P0 data | Definisi origin TEM/MUK/CAW, perbedaan cakupan preset, dan independensi spesimen belum dikonfirmasi | **Tahap 2** |
| T0-04 | P1 firmware | Timing baca ADC sebelum transisi fase dapat membuat atribusi sampel batas fase keliru | **Tahap 1** |
| T0-05 | P1 platform | USB vs UART GPIO untuk Raspberry Pi, ketersediaan PD2/PD3 pada PCB, dan translator 3,3 V | **Tahap 7** |
| T0-06 | P1 validasi | TFT final, kabel fisik, EEPROM dan kontrol valve/pompa belum diverifikasi | **Tahap 1 / 9** |
| T0-07 | P0 ML | 62 fitur untuk 86 file berkelompok; model MQ3 dan generalisasi prospektif belum tervalidasi | **Tahap 3–6 / 10** |

**Status Tahap 0:** inventaris dan baseline kontrak offline terdokumentasi, pengujian statis dapat diulang. **Keputusan fisik dan semantik label masih terbuka**, sudah diberi pemilik tahap dan bukan bukti integrasi E2E.

Verifikasi ulang kontrak: `python scripts/test_stage0_contract.py`; tetap jalankan kompilasi PlatformIO, validasi CSV dan pemeriksa HMI sesuai `AGENTS.md`.

## Catatan perkembangan Tahap 1 (9 Oktober 2026)

- **T0-01 (implementasi software):** `#pin_scan;` telah diubah menjadi respons `PIN_SCAN_DISABLED`, tanpa pemindaian pin. Perintah `#valve_on/off/test;` dinonaktifkan secara default. Tetap memerlukan verifikasi bench untuk keselamatan alat.
- **T0-02 (implementasi software):** event `ACQ_START` mode `ai_test` tidak lagi menyalurkan label yang berasal dari UI. Mode `labeled_data` tetap kompatibel dengan listener.
- **T0-04 (implementasi software):** pada `adsCallback`, sampel dibaca/dikirim dahulu dengan fase aktif kemudian state machine melakukan transisi dan mengeluarkan event. Simulasi 1 Hz ideal PASS, tetapi tidak membuktikan dinamika valve/sensor pada hardware.
- Risiko lain (T0-03, T0-05, T0-06, T0-07) **tetap terbuka**. Perubahan kode belum diunggah ke MCU fisik pada sesi ini.
