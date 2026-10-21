# Analisis awal gabungan Light–Medium–Dark B60–B68

## Cakupan dan hasil

Audit ulang 112 CSV pada `01_VALID_GABUNGAN` dilakukan tanpa mengubah file. Di antaranya, 111 CSV memiliki batch B60–B68 (satu CSV MING Light B69 dikeluarkan). Dari kandidat tersebut, 78 file dipilih untuk overlay dari lima origin yang memiliki setidaknya lima **batch unik** di tiap roast: GAW (5 Light, 5 Medium, 7 Dark), GRB (5/5/5), TEM (5/5/5), CAT (5/5/6), dan TOR (5/5/5). Setiap kurva merepresentasikan satu CSV 900 titik, bukan rata-rata.

MING tidak eligible: hanya 4 batch Light B60, B66, B67, B68, walaupun tersedia lima Medium dan lima Dark pada rentang itu. Jika kelak ditambah satu Light valid B60–B68, audit/plot dapat dijalankan ulang dalam folder keluaran **baru**.

Duplikasi definisi batch dalam data valid: `M-GRB_B60__NEW_9645c0fc1e.csv` dan `M-TEM_B62_20261019_175906.csv` tidak dimasukkan karena terdapat rekaman kanonis dengan pasangan origin/roast/batch yang sama, sedangkan independensi ulangan tersebut tidak dikonfirmasi. Semua tetap tercatat di `duplicate_same_batch_qa.csv` dan `input_provenance.csv`.

## Deskripsi metodologi numerik

`sensor_separation_diagnostics.csv` memberikan fitur **per rekaman**, bukan per detik dan bukan per siklus sebagai replika independen:

- **Respons collecting**: rata-rata (mean 5 titik collecting − median 5 titik purging terakhir sebelumnya), dirata-ratakan pada 30 siklus setiap rekaman.
- **Baseline t0**: nilai ADC pada purging siklus 1, sample_idx 25.
- **Mean collecting t0 normalized**: rerata ADC collecting 30 siklus dikurangi ADC(t0) setiap rekaman.
- **Drift**: ADC akhir dikurangi ADC awal dalam satu rekaman.
- **Between/within ratio**: variasi antar-rerata roast dibagi variasi di dalam kelas roast untuk fitur rekaman itu. Skor ini *deskriptif*, bukan akurasi klasifikasi atau uji signifikansi.
- **Three-ranges overlap**: apakah rentang min–max ketiga kelas memiliki irisan bersamaan. Ketiadaan irisan bersama **tidak otomatis** berarti ketiga kelas terpisah sempurna secara berpasangan.

## Temuan per origin

| Origin | Sensor teratas menurut kontras respons collecting | Between/within ratio | Irisan rentang ketiga kelas | Observasi |
|---|---|---:|---|---|
| GAW | TGS2611 | 1,12 | Ada | Medium rata-rata lebih tinggi dari Light dan Dark, tetapi rentang rekaman banyak overlap |
| GRB | TGS2611 | 1,01 | Ada | Dark rata-rata lebih tinggi pada respons collecting, tetapi overlap tetap ada |
| TEM | TGS2611 | 13,30 | Tidak ada irisan bersama | Sinyal perbedaan antar-roast relatif kuat; butuh verifikasi antar-perangkat dan pengambilan ulang |
| CAT | TGS2611 | 1,42 | Tidak ada irisan bersama | Rata-rata respons Light < Medium < Dark, tetapi ini belum membuktikan generalisasi |
| TOR | TGS2602 | 1,34 | Ada | Rata-rata Light < Medium < Dark, dengan overlap individual yang masih nyata |

Untuk versi t0 normalized, skor antar-roast terbesar yang diamati pada ringkasan **rerata collecting − t0** masing-masing origin adalah:

| Origin | Sensor t0 normalized tertinggi | Between/within ratio | Irisan tiga rentang |
|---|---|---:|---|
| GAW | MQ135 | 0,39 | Ada |
| GRB | TGS822 | 0,64 | Ada |
| TEM | TGS822 | 1,96 | Tidak ada irisan bersama |
| CAT | TGS822 | 1,28 | Tidak ada irisan bersama |
| TOR | TGS822 | 1,19 | Ada |

**Jangan menganggap skor dua jenis fitur sebagai perbandingan metode yang setara:** respons collecting relatif pada purge setiap siklus berbeda definisinya dari rerata collecting − t0 awal. Grafik RAW ADC dan ΔADC t0 tetap perlu diperiksa secara visual berdampingan. Normalisasi t0 menghilangkan offset baseline awal, tetapi tidak menghilangkan drift atau efek perangkat.

Sebagai tanda besarnya variasi baseline, perbedaan *rerata kelas* t0 paling besar untuk GRB pada TGS822 mencapai ~3916 ADC, dan pada GRB MQ8 ~3222 ADC. Perbedaan ini tidak dapat diatribusikan ke roasting saja tanpa catatan kalibrasi, instrumen, dan lingkungan.

Kesamaan respons antar-rekaman masih besar: rentang respons collecting dari ketiga kelas beririsan bersama pada 43 dari 50 kombinasi origin–sensor; menggunakan metrik rerata collecting terhadap t0, 47 dari 50 kombinasi juga beririsan. Bahkan ketika tidak ada irisan bersama, pasangan kelas individual masih mungkin overlap.

Besarnya drift juga harus diperiksa: pada TGS822, rentang selisih *rerata kelas* untuk drift ADC akhir–awal melebihi 1300 ADC pada seluruh lima origin. Karena drift dan urutan batch dapat berpengaruh kuat, ranking sensor yang tampak berbeda secara visual bisa berubah setelah kontrol terhadap device ID, baseline, dan waktu.

## Implikasi pengembangan AI

TGS2611 (khususnya TEM), TGS822 (t0 normalized TEM/CAT), serta TGS2602 (TOR) dapat dijadikan kandidat **analisis fitur berikutnya**, bukan kesimpulan sensor terbaik secara universal. Bandingkan distribusi fitur per rekaman pada fase collecting; audit perangkat, spesimen, dan urutan pengujian; evaluasi split berdasarkan sesi/spesimen/alat, bukan sampling acak siklus. Jangan menggunakan grafik overlay sebagai klaim akurasi klasifikasi.

## Grafik dan QA

- Grafik RAW: `01_RAW_LMD_MERGED/<ORIGIN>/`, 10 PNG × 5 origin.
- Grafik ΔADC t0: `02_T0_NORMALIZED_LMD_MERGED/<ORIGIN>/`, 10 PNG × 5 origin.
- Semua PNG mempertahankan 900 titik setiap rekaman, menggunakan waktu firmware dan warna roast konsisten.
- `plot_index.csv` memetakan setiap grafik pada sumber; `input_provenance.csv` memuat semua 112 file dan alasan selection/exclusion; `baseline_t0_per_sensor.csv` mencatat 780 baseline sensor t0 dari 78 file.
- Pemeriksaan final: 100 PNG, 100 plot_index entries, 780 baseline t0, checksum sumber tak berubah. Detail unit-test berada di `scripts/test_plot_lmd_origin_b60_b68.py`.
