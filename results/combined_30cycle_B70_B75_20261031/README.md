# Penggabungan data 30 siklus: arsip lama + B70 sampai B75

Audit ulang 238 berkas; 233 valid disalin ke `01_VALID_GABUNGAN`, 5 dikarantina melalui manifest (tidak disalin untuk AI).

Semua input lama dan baru bersifat read-only, divalidasi ketat terhadap 900 sampel, 30 siklus × (25s purging + 5s collecting), timing, metadata, receiver quality JSON, SHA256 dan fingerprint sinyal. File incomplete **tidak diinterpolasi** agar dapat dianggap sebagai sampel utuh. Detail ada di `quarantined_records.csv`.

Karena dua pasangan rekaman lama menggunakan origin+roast+batch yang sama, hanya satu per grup dihitung independen saat training. Data yang tidak memiliki device_id (arsip lama) diberi `UNKNOWN`, tidak diimputasi dari kelas.
