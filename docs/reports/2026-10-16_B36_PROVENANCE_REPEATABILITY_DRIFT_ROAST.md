# B36 — audit provenance, repeatability, drift dan perbandingan roast

**Sumber:** 18 CSV B36 terbaru di root `data/raw/`, masing-masing lima siklus, sepuluh kanal ADC. Seluruh 18 file lulus pemeriksaan struktur pada tahap audit sebelumnya. Tidak ada CSV asli atau firmware yang diubah.

## 1. Provenance — NOT VERIFIED

Terdapat nama file, `sample_id`, label UI roast/origin, data ADC dan SHA256 per file. Namun **tidak ada bukti eksternal yang ditemukan** untuk ID spesimen fisik, lot kopi, batch proses roasting, sesi operator, metode validasi origin/tingkat roasting maupun tanda tangan reviewer independen. Label UI bukan bukti label ground truth fisik. Karena itu **0/18 spesimen berstatus provenance-verified**. `results/b36_signal_provenance_20261016/provenance_review.csv` mencatat field bukti yang harus dilengkapi tanpa merekayasa nilai. Walaupun distribusi roast pilihan UI seimbang (6 dark, 6 light, 6 medium), hal itu bukan bukti independensi antarspesimen.

## 2. Metode pengukuran

Per siklus/kanal: baseline = median lima sampel terakhir fase purging, response = rerata collecting, delta = response - baseline, relative_delta = delta / max(abs(baseline), 1). Repeatability dilaporkan sebagai CV relatif atas lima nilai `relative_delta` per file/kanal (simpangan baku sampel / abs(rerata)). Drift baseline = 100 × (baseline siklus kelima − baseline siklus pertama)/abs(baseline siklus pertama). Seluruh perhitungan bersifat **deskriptif**, bukan uji pemisahan label secara konfirmatori.

## 3. Repeatability dan drift

| Kanal | Median CV antarsiklus | Median |drift baseline| |
|---|---:|---:|
| TGS822 | 23,74% | 18,89% |
| TGS813 | 33,93% | 11,58% |
| MQ8 | 12,76% | 8,26% |
| TGS816 | 12,66% | 5,25% |
| TGS2620 | 13,56% | 4,76% |
| TGS2602 | 18,15% | 1,29% |
| TGS2611 | 72,38% | 0,45% |
| MQ135 | 76,45% | 0,12% |
| MQ3 | 233,75% | 0,09% |
| TGS2600 | 411,79% | 0,07% |

TGS822 dan TGS813 menunjukkan perubahan baseline yang besar, perlu kajian carryover, pemanasan sensor, kondisi udara purging, dan drift urutan waktu. Angka CV pada MQ3/TGS2600 **tidak boleh dipakai untuk menyimpulkan sensor buruk tanpa meninjau nilai absolut**, karena denominator rerata respons sangat dekat nol sehingga CV meledak. Tiap lima siklus pada file yang sama **bukan lima sampel kopi independen**.

## 4. Perbedaan respons dark/light/medium (eksploratif saja)

Median respons relatif (rerata lima siklus per file, lalu median atas enam file per label UI):

| Kanal | Dark | Light | Medium |
|---|---:|---:|---:|
| TGS822 | 0,10324 | 0,08926 | 0,10953 |
| TGS2620 | 0,06186 | 0,03679 | 0,05618 |
| TGS2602 | 0,05613 | 0,02547 | 0,04551 |
| MQ8 | 0,04571 | 0,03048 | 0,04297 |
| TGS816 | 0,04941 | 0,02666 | 0,04403 |
| TGS813 | 0,02402 | 0,01130 | 0,02151 |

Pada keenam kanal ini light cenderung lebih rendah dibanding dua label UI lainnya, tetapi **tidak ada dasar untuk menyatakan pola disebabkan tingkat roasting**: origin, identitas lot, urutan pengambilan, spesimen dan kondisi waktu belum terkontrol. Dataset ini sudah dilihat dalam analisis per-roast sehingga **tidak boleh digunakan sebagai blind_final yang tetap benar-benar buta**. Jangan memilih kanal/model/threshold berdasarkan tabel ini lalu mengukur akurasi pada file yang sama.

## 5. Tindak lanjut berurutan

1. Minta catatan asli akuisisi kepada operator; cocokkan tiap SHA256 file dengan lot, spesimen unik, roast-batch, waktu/sesi, foto/rekaman fisik, referensi origin dan bukti roast, lalu minta reviewer independen memeriksa. Tidak ada pengisian field berdasarkan nama file saja.
2. Evaluasi apakah purging 25 detik cukup untuk mengembalikan TGS822/TGS813 mendekati baseline awal. Lakukan blank/reference sebelum–sesudah tiap sampel dan studi pemulihan waktu; tetapkan batas toleransi sebelum eksperimen.
3. Ukur baseline intra-siklus dan antarfile, pengaruh temperatur/RH, serta urutan pengukuran; lakukan pengulangan independen dengan sampel dan sesi berbeda.
4. Standarkan protokol purging/collecting, pemanasan sensor, pembersihan chamber dan urutan random antar-roast agar sesi tidak menjadi proxy label.
5. Setelah provenance diverifikasi, lakukan analisis beda roast dengan unit sampel = spesimen independen, membandingkan origin yang sama, melaporkan interval ketidakpastian; simpan data blind_final baru yang **belum pernah dipakai dalam eksplorasi**.

Artefak lengkap: `results/b36_signal_provenance_20261016/{cycle_responses.csv,per_file_repeatability_drift.csv,channel_quality_summary.csv,roast_descriptive_comparison.csv,provenance_review.csv,summary.json}`. Semua hasil **diagnostic/no-go**, bukan hasil model atau bukti independensi spesimen.
