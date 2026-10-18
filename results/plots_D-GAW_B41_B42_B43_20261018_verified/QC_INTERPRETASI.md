# QC dan interpretasi D-GAW B41–B43 (18 Oktober 2026)

## Lingkup dan integritas data

- Sumber hanya-baca: `data/raw/D-GAW_B41.csv`, `D-GAW_B42.csv`, `D-GAW_B43.csv`.
- Kode yang dipakai: `scripts/plot_d_gaw_b41_b43.py`, dijalankan ke direktori hasil baru `results/plots_D-GAW_B41_B42_B43_20261018_verified/`.
- **PASS (offline/data):** validator canonical untuk 30 siklus; 63 PNG dihasilkan dan dibuka; hash SHA256 ketiga input cocok dengan `summary.json` setelah eksekusi; 0 sel ADC kosong dan tidak ada baris sensor parsial.
- **Tidak melakukan:** interpolasi, smoothing, resampling, pemotongan sampel, pengubahan CSV asli, penggunaan USB COM, flashing, kalibrasi, atau aktivasi pompa.

Perintah reproduksi dari root repository (pilih nama direktori **baru** karena script menolak overwrite):

```powershell
python -c "import sys;sys.path.insert(0,'scripts');import plot_d_gaw_b41_b43 as p;p.OUT=p.ROOT/'results'/'plots_D-GAW_B41_B42_B43_RERUN_BARU';p.main()"
```

| Indikator | B41 | B42 | B43 |
|---|---:|---:|---:|
| Siklus | 30 | 30 | 30 |
| Sensor rows | 908 | 956 | 900 |
| Purging rows | 754 | 780 | 750 |
| Collecting rows | 154 | 176 | 150 |
| Timestamp sampel pertama–terakhir (detik) | 907 | 955 | 899 |
| Rata-rata selang awal purging antarsiklus (detik) | 30,276 | 31,862 | 30,000 |
| Sampel ADC yang kosong | 0 | 0 | 0 |

**Penjelasan timing:** B41 dan B42 adalah data dengan pergantian fase yang menyebabkan kelebihan sampel dan durasi; B43 berisi tepat 30 × (25 sampel purging + 5 collecting) = 900 sampel. Rentang timestamp B43 899 detik adalah selisih 900 pengukuran 1 Hz, **bukan** bukti bahwa seluruh operasi fase hanya berjalan 899 detik. Bukti durasi aktif dari event `ACQ_COMPLETE.elapsed_active_ms` harus dibedakan dari timestamp sampel. Laporan fisik historis menyebut 900.002 ms, tetapi log event tersebut tidak ditemukan kembali pada file `logs/acquisition_service.log*` yang diperiksa dalam audit ini.

## Normalisasi dan cara membaca plot

- Folder `01_per_batch_per_sensor/`: 30 grafik sensor masing-masing batch (10 sensor × 3 batch), dengan fase collecting ditandai berdasarkan timestamp sampel.
- `02_cross_batch_raw/`: 10 overlay ADC mentah berdasarkan detik dari sampel pertama *masing-masing* batch. Semua nilai dan ketidakseragaman durasi dipertahankan.
- `03_cross_batch_t0_normalized/`: 10 overlay `ADC(t) - ADC(t0)` dengan `t0` = pembacaan **purging terakhir siklus 1** dalam setiap batch, bukan clean-air baseline eksternal.
- `04_cycle_response/`: 10 grafik perubahan rata-rata collecting terhadap median lima sampel purging terakhir, dibandingkan pada indeks siklus 1–30 (perbandingan yang lebih adil daripada menyamakan waktu absolut firmware lama/baru).
- `05_environment/`: suhu dan kelembapan. `06_timing/`: selang permulaan purging tiap siklus.
- **Perbedaan penting:** `t0` pada B41/B42 adalah `sample_idx=26` sekitar 25 detik sejak sampel awal, sedangkan B43 adalah `sample_idx=25` sekitar 24 detik. Ini akibat cara timestamp 1 Hz memotret akhir purging; `t0` dimaknai sebagai titik sensor terakhir sebelum collecting, **bukan** secara literal index 26 pada semua file. Sumbu x relatif t0 tidak berarti waktu saklar katup telah terukur persis.

## Interpretasi ADC (bukan klasifikasi roasting)

Median perubahan per siklus = `mean(collecting) - median(lima sampel purging terakhir)`, satuan ADC mentah:

| Kanal | B41 | B42 | B43 |
|---|---:|---:|---:|
| TGS822 | +752,40 | +926,50 | +448,10 |
| TGS2620 | +408,50 | +105,08 | +37,40 |
| TGS2602 | +391,90 | +33,17 | +27,70 |
| MQ8 | +511,60 | +154,25 | +20,10 |
| TGS813 | +126,30 | +119,67 | -46,20 |
| TGS816 | +540,30 | +215,33 | +107,50 |

Respons beberapa kanal berubah besar antarbatch, termasuk perubahan tanda TGS813. Hal ini perlu diselidiki sebagai variasi antar-run, perubahan baseline, kondisi sampel/sistem, atau drift; tidak cukup bukti menentukan penyebabnya dari CSV saja. Semua tiga batch adalah **D-GAW/Dark**, sehingga grafik ini **tidak dapat** membuktikan kemampuan membedakan Light, Medium, dan Dark. Jangan melatih atau mengklaim model produksi berdasarkan hasil overlay ini.

## Bukti perangkat lunak dan batas

- **PASS (build):** `pio run -e mega2560`; flash 33.998 byte dan RAM 3.867 byte.
- **PASS (offline):** `test_absolute_timing_firmware.py`, `test_take30_contract.py`, `test_acquisition_integrity.py`, `test_12_page_take_data_contract.py`, `test_usb_autodetect.py`, `test_receiver_bundle.py`.
- **Belum diuji ulang (fisik):** aktuator, Nextion di alat, penulisan CSV live, durasi event MCU, dan konektivitas Windows 10 ProBook. Status receiver lokal terbaca `waiting_for_port`, COM5, saat inspeksi pasif; tidak membuka port atau mengintervensi receiver.
- Masalah Windows 10 dengan `usb_not_found` / hanya Bluetooth COM3–COM4 tetap **outstanding** dan memerlukan pemeriksaan enumerasi/driver FT232R di laptop tersebut.
- Artefak `results/plots_D-GAW_B41_B42_B43_20261017/` dan `..._20261018/` lama dipertahankan. Lihat `plot_index.csv`, `cycle_response_metrics.csv`, `input_provenance.csv`, dan `summary.json` untuk sumber yang dapat diaudit.

## Langkah lanjutan

1. Tinjau grafik `04_cycle_response/` dan `03_cross_batch_t0_normalized/` untuk pola drift/recovery tiap sensor.
2. Tambahkan bukti kondisi fisik (volume dan masa kopi, kebersihan chamber, suhu/kelembapan, alat, waktu, dan identitas spesimen) sebelum menafsirkan penyimpangan antarbatch.
3. Untuk AI roasting, kumpulkan Light/Medium/Dark pada origin dan konfigurasi yang sama; evaluasi per batch/spesimen secara independen, tanpa random split per-siklus.
4. Investigasi enumerasi FT232R Windows 10 dari Device Manager; jangan paksa koneksi ke COM Bluetooth.
