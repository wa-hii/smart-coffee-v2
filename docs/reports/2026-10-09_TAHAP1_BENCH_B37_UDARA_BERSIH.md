# Verifikasi bench B37 — akuisisi udara bersih melalui Nextion

**Tanggal:** 9 Oktober 2026

**Konfirmasi pengguna/operator:** pengujian dijalankan dari Nextion dengan selang ditempatkan di **udara bersih** pada batch B37. Tidak ada observasi langsung agen terhadap penempatan selang, posisi valve, aktuator, UI atau versi firmware yang ter-flash.

**Metode audit:** membaca log listener `lcd_acquisition_service.py`, dua CSV final B37, checksum dan hasil validator. **Tidak membuka COM5**, mengirim perintah firmware, melakukan flash, mengubah kalibrasi, atau memodifikasi file mentah.

## 1. Bukti serial dan sesi

Listener sebelumnya telah teramati melalui `pythonw.exe` PID 16472 pada **COM5@115200**. Log aplikasi berisi:

| File CSV final | ACQ START (WIB) | ACQ COMPLETE (WIB) | Baris | Validator umum |
|---|---|---|---:|---|
| `L-MING_B37.csv` | 18:35:43,026 | 18:38:13,410 | 150 | PASS |
| `M-MING_B37.csv` | 18:51:13,278 | 18:53:45,860 | 152 | PASS |

Sumber perintah Nextion diterima sebagai kesaksian operator. Log listener membuktikan event `ACQ_START`/`ACQ_COMPLETE` dari firmware melalui serial, **bukan** secara independen membuktikan tombol tertentu di HMI. Tidak tersedia telemetri fisik untuk arah valve/pompa dan keakuratan fase 25/5 detik.

## 2. Hasil verifikasi CSV secara read-only

| Pemeriksaan | `L-MING_B37.csv` | `M-MING_B37.csv` |
|---|---|---|
| SHA256 | `e7589d02ce97bbafad27ed361221eb0246939f8e41d0df04b963865f56c4c468` | `558f7e91a320bc6f122888ddf104c39532d166f7bbda4be02e8e5118d6d8cb6e` |
| Validator canonical | **PASS** | **PASS** |
| Validator bench ketat (5 × 25/5 sampel, tanpa pause) | **PASS** | **FAIL** |
| Purging 5 siklus | 25,25,25,25,25 | 25,25,25,25,25 |
| Collecting 5 siklus | 5,5,5,5,5 | **6,5,5,5,6** |
| Total frame sensor | **150** | **152** |
| Indeks sampel tiap fase | Berurutan mulai 1 | Berurutan mulai 1; ekstra collecting juga berurutan |
| Interval antar-timestamp MCU | **979–1004 ms** | **996–1004 ms** |
| Rentang suhu (°C) | 27,32–27,74 | 26,98–27,39 |
| Rentang kelembapan (%RH) | 56,22–56,74 | 54,35–56,30 |
| Nilai ADC null/0/32767 | Tidak ditemukan | Tidak ditemukan |
| Baris metadata-only / parsial | Tidak ditemukan | Tidak ditemukan |

**Interpretasi jumlah sampel:** validator canonical mengizinkan collecting **4–7 sampel per fase** karena sampling berkala dan pemrosesan event bisa memiliki jitter. SOP bench pasif ketat membandingkan dengan target nominal **5**; M-MING mendapat dua collecting tambahan. Angka ini **bukan otomatis data rusak, duplikasi, atau kesalahan valve**. Perlu trace event fase, versi firmware terpasang, dan observasi/alat ukur aktuator untuk menjelaskan apakah terjadi tambahan pembacaan pada batas fase.

**Interpretasi timestamp:** selang antar-sampel MCU mendekati 1 detik. Nilai `timestamp` berasal dari `millis()`; tidak dapat membuktikan gerak fisik valve, peralihan aliran, atau kestabilan udara bersih. Keberadaan suhu/kelembapan dalam rentang wajar juga bukan bukti kalibrasi SHT30.

**Verifikasi regresi setelah audit:** build PlatformIO `mega2560` dan `nextion_test` **PASS**; HMI contract 12 halaman/23 event **PASS**; test Tahap 0, Tahap 1, ekstraksi fitur, dan fixture QA bench **PASS**; `compileall` **PASS**. `scripts/test_acquisition_suite.py` memeriksa **89/89 file B32+ (termasuk dua B37), seluruhnya PASS validator canonical**, sedangkan inventaris ilmiah terbatas B32–B35 tetap **87/87 PASS**. Ini tidak mengubah hasil ketat M-MING B37 yang tetap FAIL dua sampel lebih banyak.

## 3. Ketidaksesuaian label — wajib dikunci sebelum pelatihan AI

Menurut operator, medium yang diuji adalah **udara bersih**, sedangkan antarmuka tetap memilih kode kopi `L-MING` dan `M-MING`, sehingga CSV final memiliki kolom `sample_id`, `roast_level`, serta `origin` yang **bukan label fisik sebenarnya**.

**Keputusan provenance:** kedua file **BENCH_ONLY / NOT_ELIGIBLE_FOR_COFFEE_TRAINING**. File mentah disimpan utuh. Daftar pengecualian ber-hash di `data/analysis/bench_only_exclusions.csv`. Jangan memasukkannya ke dataset roast/origin, baik training maupun evaluasi. Jika kelak digunakan sebagai baseline udara bersih, buat dataset turunan dengan metadata eksperimen baru yang eksplisit; jangan menimpa label dalam raw.

Ekstraktor `scripts/extract_b32_features.py` saat ini secara eksplisit hanya memilih B32–B35, sehingga kedua file B37 tidak otomatis terambil. Pipeline masa depan yang melibatkan batch B37 harus memeriksa manifest pengecualian.

## 4. Status SOP Tingkat B dan tindak lanjut

| ID SOP | Hasil yang didukung | Status |
|---|---|---|
| B01 | Listener/baud teramati; versi firmware/HMI ter-flash dan skematik PCB tidak dibuktikan | **SEBAGIAN** |
| B02 | 10 kanal ADC dan SHT30 tertulis tanpa null, 0 atau saturasi | **PASS untuk kelengkapan data**, kalibrasi belum terverifikasi |
| B03 | Lima siklus dicatat lengkap; 150 vs 152 sampel | **SEBAGIAN**, timing fisik valve/pompa belum diverifikasi |
| B04 | Dua file final dan validator canonical PASS | **PASS** |
| B05 | Interval `millis()` konsisten; satu file meleset dari target sampel ketat | **SEBAGIAN** |
| B06 | Mulai akuisisi dari Nextion menurut laporan operator; navigasi lengkap, pause/cancel, visual belum dicatat | **SEBAGIAN / belum diverifikasi independen** |
| B07 | Stop/pause/resume, reboot, fault injection, dan fail-safe belum diuji | **NOT RUN** |
| B08 | CSV final tersedia; tidak ada tindakan rollback/maintenance | **SEBAGIAN** |

**Status Tahap 1: PASS pada jalur pengiriman data dan penyimpanan dua sesi; NO-GO untuk klaim validasi hardware menyeluruh.**

**Tindak lanjut terprioritas:** (1) dokumentasikan firmware/HMI versi aktual dan kesesuaian wiring; (2) ukur perpindahan valve dan timing 25/5 detik dengan stopwatch/video atau pengukur sinyal saat uji terkontrol; (3) telusuri dua sampel ekstra collecting pada M-MING dengan log fase dan `TaskScheduler`; (4) konfirmasi respon pause/cancel/fail-safe jika SOP berizin; (5) ubah prosedur dan identitas pengambilan data bench sehingga tidak memakai label kopi palsu.

Tidak dilakukan perubahan fisik/firmware pada sesi validasi ini.

### Addendum — konfirmasi operator sebelum Tahap 2

Operator menyatakan **pompa/valve berpindah mengikuti durasi 25 s purging + 5 s collecting** serta **Nextion berjalan sampai halaman selesai tanpa error**. B03 dan B06 memiliki **bukti observasi operator untuk fungsi utama normal**; pengukuran durasi dengan logic analyzer atau pengukuran valve independen belum tersedia, dan masalah **152 frame M-MING** tetap harus ditelusuri. Status B07 (fail-safe/negative cases) tetap NOT RUN. Tidak ada klaim seluruh Tahap 1 sudah hardware-certified. Pemeriksaan berikutnya berupa audit data read-only Tahap 2 tanpa membuat sampel fisik baru.
