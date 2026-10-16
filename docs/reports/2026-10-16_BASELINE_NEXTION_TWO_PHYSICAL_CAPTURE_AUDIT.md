# Audit fisik baseline LCD Nextion — dua sesi 60 detik (16 Oktober 2026)

**Status:** dua sesi **CAPTURE PASS**; sesi kedua **B0 CANDIDATE** untuk pengujian kopi berikutnya, **bukan certified clean-air baseline / R0 calibration**. Audit dilakukan pada file lokal saja tanpa membuka COM5, mengontrol valve, atau mengedit data asli.

## 1. Bukti akuisisi dan integritas

| Properti | Sesi 1 | Sesi 2 |
|---|---|---|
| Start pada log listener | 18:53:10 WIB | 18:55:22 WIB |
| COMPLETE pada log | 18:54:10 WIB | 18:56:23 WIB |
| File | BASELINE_20261016_185310_e636759c6edb.csv | BASELINE_20261016_185522_126dd90194e8.csv |
| Ukuran | 4.750 byte | 4.751 byte |
| Sensor frame | 60/60 | 60/60 |
| First-to-last timestamp | 59,001 s | 59,000 s |
| Interval antar-sampel | 955–1.046 ms | 999–1.001 ms |
| Missing fields | 0 | 0 |
| QC JSON | Ada; SHA cocok | Ada; SHA cocok |
| Kriteria drift ±1% per sensor | 8/10 | **10/10** |
| Suhu | 30,66–30,84°C | 30,80–30,98°C |
| RH | 57,93–58,43% | 57,90–58,34% |

SHA256 sesi 1: `873b0efbfe946db6ff28380e10acc35a173eaec72994b7609c74b4510c004654`.

SHA256 sesi 2: `8fe5f0eb38b1fd157bd2e9ba909232cb3ff018b48637c6322c1a5810c51cbdc3`.

Validasi: CSV 14 kolom (timestamp, sample_idx, 10 ADC, suhu, RH); indeks 1..60 kontigu; interval memenuhi kontrak 900–1100 ms; SHA-256 identik dengan JSON QC tiap sesi. Kedua capture selesai melalui jalur Nextion → ATmega2560 → COM5 → listener dan diterbitkan tanpa duplikasi.

## 2. B0 fisik yang diukur dan perbandingan

**Definisi B0:** median 10 sampel **terakhir** dari 60 sampel per kanal (bukan R0 resistansi sensor pada EEPROM). Persentase antar-sesi: (B0 kedua − B0 pertama)/B0 pertama × 100%. Drift dalam sesi: (median 10 terakhir − median 10 pertama)/median 10 pertama × 100%.

| Sensor | B0 1 (ADC) | B0 2 (ADC) | Delta antar-sesi | Drift 1 | Drift 2 |
|---|---:|---:|---:|---:|---:|
| TGS822 | 11036 | 10998 | −0,344% | −0,911% | −0,145% |
| MQ135 | 2909 | 2905 | −0,138% | −0,120% | −0,103% |
| MQ3 | 2901 | 2898 | −0,103% | +0,035% | −0,035% |
| TGS2611 | 8236 | 8295 | +0,716% | +0,128% | +0,224% |
| TGS2620 | 8820 | 8805 | −0,170% | **−1,820%** | +0,114% |
| TGS2600 | 2883 | 2884 | +0,035% | −0,035% | +0,069% |
| TGS2602 | 9062 | 9081 | +0,210% | −0,652% | +0,226% |
| MQ8 | 12365,5 | 12334 | −0,255% | −0,339% | −0,057% |
| TGS813 | 12808 | 12715 | −0,726% | **−1,314%** | −0,024% |
| TGS816 | 13349,5 | 13327 | −0,169% | −0,455% | +0,053% |

Dalam sesi 1, TGS2620 dan TGS813 melebihi kriteria drift eksploratif ±1%; dalam sesi 2 semua sensor memenuhi. Antar-sesi, nilai B0 berbeda maksimum **0,7261%** (TGS813), berikutnya TGS2611 **0,7164%**. Ini **konsistensi numerik awal**, bukan bukti bebas carryover/warm-up/sensitivitas gas.

## 3. Keputusan dan batasan

1. **PASS capture:** kedua file lengkap, berurutan, sensor+lingkungan tersedia, checksum terverifikasi, dan logger host mencatat COMPLETE.
2. **B0 pilihan awal:** nilai dari **sesi 2** lebih stabil dalam sesi untuk kesepuluh kanal, tetapi berstatus **CANDIDATE** sampai operator membuktikan jalur udara bersih, waktu warm-up dan kondisi chamber. Ambang ±1% adalah batas eksploratif, bukan standar kalibrasi sensor bersertifikasi.
3. Kedua baseline diambil **setelah** D-GAW_B41 (B41 selesai 17:54 WIB, baseline baru pukul 18:53/18:55 WIB). Tidak sah menjadikan baseline tersebut sebagai bukti nilai pra-akuisisi B41. Untuk B42 dan seterusnya, lampirkan ID baseline dan metadata fisik sampel/operator pada manifest sebelum analisis.
4. Firmware menyatakan kalibrasi R0 sebelumnya **belum valid** akibat perubahan penanda EEPROM; tombol pCal hanya merekam ADC, tidak menulis R0 EEPROM. Event menyatakan `eeprom_r0_modified=false`, konsisten dengan kode, tetapi audit ini tidak mengukur EEPROM secara langsung.
5. Tidak ada klaim dataset baseline ini memvalidasi model AI, label roast, atau 30 spesimen independen; B41 tetap hanya satu sesi fisik dengan 30 repeated measurements.

## 4. Berkas pendukung

CSV raw dan JSON orisinal disimpan di `data/baseline/`. Analisis tanpa overwrite pada `results/baseline_60s_pair_qa_20261016/`: `baseline_b0_comparison.csv`, `summary.json`, dan **10 grafik** per sensor membandingkan dua run terpisah pada sumbu relatif 0–59 detik. Reproduksi dengan `python scripts/audit_baseline_pair_20261016.py` ke folder hasil yang belum ada.
