# Audit variasi, respons collecting, dan drift 30 siklus

Seluruh 112 CSV valid dibaca ulang tanpa modifikasi. Per rekaman terdapat 30 siklus; 30 siklus **bukan** 30 pengulangan independen.

## Tabel utama

- `recording_retest_priority.csv`: urutan flag yang perlu inspeksi / kandidat pengambilan ulang; **flag bukan bukti invalid**.
- `sensor_per_recording.csv`: fitur/indikator setiap sensor dari setiap CSV.
- `sensor_primary_batch_with_outlier_flags.csv`: flags dan robust z terhadap pengambilan origin+roast sejenis.
- `repeatability_per_origin_roast_sensor.csv`: variasi antar-batch unik (CV dan robust RSD dapat tidak stabil jika rerata respons mendekati nol).
- `cycle_per_sensor.csv`: 30 nilai respons collecting dan baseline purging masing-masing sensor/rekaman.
- `roast_separation_exploratory.csv`: perbedaan rerata fitur antar-roasting / dalam-roasting untuk 6 origin dengan 3 roast.
- `sensor_exploratory_ranking.csv`: agregasi antar-origin (bukan fitur/model terbaik teruji).
- `drift_to_response_heatmap.png`: nilai median drift/response per origin+sensor (tampilan log10).

## Definisi

- Setiap siklus: purging 25 titik lalu collecting 5 titik.
- Respons collecting siklus = mean(5 collecting) − median(5 titik purging terakhir).
- Baseline tiap siklus = median(5 titik purging terakhir).
- Drift run = median(baseline siklus 26–30) − median(baseline siklus 1–5).
- Drift/respons = |drift| / (median(|respons collecting 30 siklus|)+1).
- CV antar-batch dihitung dari respons mean per *rekaman unik*, bukan dari semua 900 titik.
- Robust z = 0.67449 × (x−median grup) / MAD (jika MAD nol, tidak ada flag).
- Prioritas uji ulang bersifat konservatif: sensor saturasi, >=5 kanal ekstrem vs peer, >=5 kanal drift ekstrem, atau drift dominan >=7 sensor disertai anomali antar-peer. Review mencakup >=3 kanal anomali peer, drift dominan >=5, respons awal–akhir berubah di >=5 sensor, atau suhu/RH berubah >=4 C/12 poin.
- Data dengan origin+roast+batch sama tetapi isi berbeda ditandai sebagai perlu konfirmasi independensi; hanya satu representatif dipakai untuk menghitung repeatability.
- Sensor/rekaman tanpa respons kuat **bukan** otomatis alat rusak; sensitivitas terhadap kopi mungkin kecil.
- Tidak bisa membedakan drift sensor fisik vs volatilitas kopi/chamber vs alat berbeda vs suhu/RH dari CSV saja.
- Saran uji ulang harus dikonfirmasi dengan run udara bersih, satu alat tetap, urutan sampel diacak, kondisi lingkungan, kontrol residu chamber, dan minimal lima preparasi sampel independen per kelas.
