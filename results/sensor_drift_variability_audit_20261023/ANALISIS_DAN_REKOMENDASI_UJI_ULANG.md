# Audit variasi, drift, repeatability, dan rekomendasi uji ulang — Smart Coffee E-Nose v2

**Tanggal analisis:** 23 Oktober 2026

**Input:** `data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019/HASIL_GABUNGAN_20261021/01_VALID_GABUNGAN/`
**Kondisi:** 112 CSV diverifikasi ulang. Tidak ada file sumber yang diedit/dihapus.

## Ringkasan eksekutif

**Tidak ada CSV yang wajib dibuang atau diulang atas dasar struktur pengambilan**: seluruh 112 file lolos ketentuan 900 pembacaan, 30 siklus, 25 detik purging + 5 detik collecting, integritas sensor dan waktu. Namun, lolos struktur **bukan** berarti kualitas responsnya sudah konsisten untuk AI.

Hasil screening deskriptif setiap 10 sensor, per rekaman dan per siklus:

| Status screening | Jumlah file | Tindak lanjut |
|---|---:|---|
| `PRIORITAS_UJI_ULANG` | **10** | Cek grafik detail, baseline, kebersihan chamber dan alat; lakukan uji pengulangan terkontrol |
| `PERLU_REVIEW` | **60** | Tinjau drift/variabilitas secara bertahap; jangan otomatis dibuang atau diulang |
| `TIDAK_ADA_FLAG_BESAR` | **40** | Layak dipertahankan sebagai kandidat analisis lanjutan, tetap evaluasi dampak alat/sesi |
| `KONFIRMASI_REPLIKASI_BATCH` | **2** | Konfirmasi apakah sesi, spesimen dan alat berbeda; jangan hitung sebagai batch independen |

Data memiliki **110 kombinasi origin–roast–batch unik** dari total 112 CSV; dua berkas ekstra merupakan pengambilan berbeda dengan identitas batch yang sama. Pemeringkatan variasi antar-batch hanya memakai satu representatif per kombinasi, sehingga terdapat 1.100 baris metrik sensor-recording utama dan 33.600 baris metrik siklus-sensor (112 × 30 × 10).

**Indikator utama drift:** 533 dari 1.100 pasangan recording–sensor memiliki |perubahan baseline awal–akhir| lebih dari 3× median |respons collecting| per siklus. Selain itu, 598 dari 1.100 pasangan memiliki median respons collecting / noise fase purging kurang dari 1,2 menurut definisi audit ini. Kedua angka adalah **indikator skrining**, bukan bukti kegagalan sensor. Rasio drift bisa sangat tinggi ketika respons collecting sensor mendekati nol.

Tidak ditemukan kanal dengan pembacaan ADC dekat 0 atau 32767 pada lebih dari 1% titik, dan tidak ditemukan missing suhu/RH. Nilai perubahan suhu *dalam satu run* paling besar sekitar 1,37 °C, kelembapan sekitar 5 poin; meskipun demikian perbedaan **antar-kelompok roasting** bisa jauh lebih besar (lihat di bawah).

## Rekomendasi pengambilan ulang per CSV

### A. Prioritas tinggi — uji ulang lebih dahulu (7 CSV)

| CSV | Dasar flag kuantitatif | Fokus diagnosis |
|---|---|---|
| **`D-CAT_B60.csv`** | Respons collecting berbeda dari peer Dark CAT pada **7 sensor** (robust z ≥ 3,5) | Ulang pada kondisi alat stabil; cek massa/sampel, seal chamber dan efek sisa kopi sebelumnya |
| **`D-TEM_B60.csv`** | Respons collecting outlier pada **6 sensor** | Bandingkan 5 Dark TEM yang lain dalam alat dan prosedur sama |
| **`L-MING_B66.csv`** | Respons outlier pada **5 sensor**, 6 sensor memiliki rasio drift/respons > 3 | Ulang Light MING setelah baseline udara bersih dan purge cukup |
| **`M-GAW_B60.csv`** | Respons outlier pada **5 sensor** dan baseline awal berbeda pada **4 sensor** | Verifikasi alat, kalibrasi, massa kopi; remeasurement Medium GAW |
| **`L-TOR_B67.csv`** | Drift lebih tinggi dari peer pada **5 sensor**, baseline awal outlier 4 sensor, drift dominan pada 9 sensor | Periksa stabilisasi, purge/chamber memory; ulang Light TOR |
| **`M-CAT_B66.csv`** | Drift lebih tinggi dari peer pada **5 sensor**, drift dominan pada 9 sensor | Uji baseline udara bersih sebelum dan sesudah; ulang Medium CAT |
| **`M-TOR_B67.csv`** | Drift lebih tinggi dari peer pada **5 sensor**, drift dominan pada 7 sensor | Ulang Medium TOR setelah verifikasi drift alat dan chamber |

### B. Perlu konfirmasi, lalu uji ulang bila masalah terulang (3 CSV)

| CSV | Dasar flag | Langkah awal |
|---|---|---|
| **`L-CAT_B62.csv`** | Baseline awal outlier pada 3 sensor, drift dominan pada 9 sensor | Cek posisi baseline t0, stabilisasi awal dan perbedaan device |
| **`M-GAW_B61.csv`** | Baseline awal outlier pada 5 sensor, drift dominan pada 7 sensor | Bandingkan profil purging dan alat dengan M-GAW B60/B66–B68 |
| **`M-MUK_B60.csv`** | Baseline awal outlier pada 3 sensor, drift dominan pada 7 sensor; perubahan respons antar-awal/akhir menonjol pada 5 sensor | Periksa baseline, kontrol aliran/purge, lalu ulang jika anomali tetap muncul |

**PENTING:** Kesepuluh berkas **masih valid secara struktur**. Status hanya menandai anomali statistik dalam kelompok origin+roast, sering dihitung dari lima pengambilan. Penyebabnya bisa variasi aroma spesimen yang nyata, gas residu, alat berbeda, suhu, kelembapan, atau stabilisasi sensor; tidak dapat dipastikan dari CSV. Jangan menghapus atau mengganti data lama. Tandai sebagai `QA_REVIEW`, lalu lakukan uji konfirmasi. Jika anomali konsisten ketika protokol terkendali, pertahankan sebagai variasi fisik yang sah; jika berasal dari gangguan yang dapat direproduksi, catat alasan eksklusi secara eksplisit.

### C. Dua rekaman dengan ID batch sama

- `M-GRB_B60.csv` dibanding `M-GRB_B60__NEW_9645c0fc1e.csv`.
- `M-TEM_B62.csv` dibanding `M-TEM_B62_20261019_175906.csv`.

File berbeda isi, tetapi identitas origin+roast+batch sama. Keduanya **tidak otomatis menjadi ulangan independen** sampai identitas alat, waktu dan spesimen dipastikan. Tidak perlu ulang jika data provenance dapat dipulihkan; cukup perbaiki metadata eksperimen dalam katalog eksternal, tanpa mengganti isi CSV historis.

## 10 sensor: variasi respons vs drift baseline

Tabel berikut dihitung dari 110 rekaman primary batch (bukan 112 termasuk pengulangan nama batch). Respons collecting = mean 5 sampel collecting dikurangi median 5 sampel purging terakhir dari siklus yang sama. Drift = median baseline siklus 26–30 dikurangi median baseline siklus 1–5. Semua angka di bawah adalah **median antar-rekaman**, bukan kisaran spesifikasi pabrik.

| Sensor | Median |respons collecting| (ADC) | Median |drift baseline| (ADC) | Median drift/respons | Respons/noise purging |
|---|---:|---:|---:|---:|
| TGS822 | 187,7 | 161,0 | **0,79** | 1,58 |
| TGS816 | 77,7 | 234,5 | 2,43 | 3,07 |
| TGS2602 | 43,3 | 213,0 | 3,72 | **9,44** |
| MQ8 | 57,0 | 168,0 | 2,64 | 1,23 |
| TGS813 | 56,0 | 284,0 | 4,42 | 0,91 |
| TGS2620 | 21,3 | 272,0 | 9,81 | 1,33 |
| **TGS2611** | **2,8** | 96,0 | **25,77** | 1,49 |
| MQ135 | 1,1 | 3,0 | 1,70 | 0,41 |
| MQ3 | 0,9 | 3,0 | 1,54 | 0,35 |
| TGS2600 | 0,85 | 2,0 | 1,28 | 0,36 |

Rasio respons/noise di sini adalah `median(|respons collecting per siklus|) / (median SD lima titik purging terakhir+1 ADC)`; **bukan SNR instrumentasi standar**. Karena MQ135/MQ3/TGS2600 memiliki perubahan collecting sangat kecil (sekitar 1 ADC), jangan langsung menyatakan rusak atau tidak berguna: beberapa fitur baseline absolut mungkin informatif, tetapi lebih rentan bocor ke identitas alat/sesi.

### Penilaian kandidat sensor untuk AI (sementara)

**TGS822** merupakan kandidat pertama yang **layak diuji**, bukan sensor terbaik yang sudah terbukti: sinyal collecting cukup besar dan pergeseran baseline relatif lebih kecil. Rasio pemisahan antar-roast terhadap variasi dalam roast untuk fitur collecting−t0 juga tampak relatif lebih tinggi secara median lintas origin (sekitar 1,01), tetapi masih bisa terjadi overlap.

**TGS2602** memiliki kontras collecting/noise purging yang kuat, dan **TGS816** juga menunjukkan kontras fase nyata. Keduanya perlu normalisasi terhadap baseline purging tiap siklus karena drift baseline relatif terhadap respons masih sering besar.

**TGS2611** dapat memiliki perbedaan rerata antar-roasting pada origin tertentu, tetapi **jangan memilihnya hanya berdasarkan grafik**: drift/respons median sekitar 25,77, sedangkan respons fase collecting khas hanya sekitar 2,8 ADC. Perbedaan yang terlihat bisa berkaitan dengan baseline, device, atau kondisi eksperimen, bukan roasting itu sendiri.

**TGS2620, MQ8, TGS813** sebaiknya dievaluasi sebagai kanal tambahan setelah koreksi baseline serta pemeriksaan noise, korelasi antarsensor, dan sensitivitas terhadap alat/sesi.

## Faktor perancu yang penting: suhu/RH *antar-kelas*

Meskipun suhu/RH dalam sebagian besar satu sesi relatif stabil, rerata suhu pada kelompok kelas berbeda cukup jauh:

| Origin | Light (°C) | Medium (°C) | Dark (°C) | Perhatian |
|---|---:|---:|---:|---|
| TEM | 27,6 | 28,2 | **32,0** | Dark sekitar **4,4 °C** lebih hangat dari Light |
| GAW | 27,8 | 29,3 | **31,0** | Dark sekitar **3,2 °C** lebih hangat dari Light |
| GRB | 28,1 | 29,8 | 26,6 | Medium sekitar **3,2 °C** lebih hangat dari Dark |

Pada CAT, rerata RH Dark sekitar **62,1%**, Medium **54,6%**, Light **57,7%**. Perbedaan lingkungan ini dapat berkorelasi dengan label roasting. Model AI mungkin mempelajari efek suhu/RH atau sesi/alat sebagai shortcut alih-alih pola volatil kopi. Tidak ada kolom identitas perangkat fisik dalam CSV, sehingga perbandingan antar-ALAT_1/2/3 **belum bisa dipertanggungjawabkan** dari berkas ini.

## Fitur yang disarankan sebelum training

Mulai dari representasi *per satu rekaman 30 siklus*, bukan 900 baris sebagai sampel independen:

1. **Cycle-local phase contrast:** `mean(collecting 5 titik)−median(5 titik purging akhir)` per siklus, lalu ringkas 30 siklus menjadi median, IQR, rata-rata dan tren.
2. **Early/late response difference:** median respons collecting siklus 26–30 dikurangi 1–5, sebagai ukuran drift sensitivitas atau adaptasi.
3. **Baseline drift:** median akhir purging siklus 26–30 dikurangi 1–5. Gunakan untuk QA dan analisis domain shift, bukan langsung sebagai sinyal kelas sampai device/sesi terkendali.
4. **Response area:** penjumlahan 5 selisih collecting−purging akhir tiap siklus, lalu ringkas per rekaman. Tidak perlu sampling ulang.
5. **Robust response variability:** MAD/IQR respons selama 30 siklus; perhatikan perubahan tanda respons di antara siklus.
6. **t0-normalized early/late summaries:** sebagai pembanding, tetapi koreksi t0 awal saja belum menghilangkan drift selama 900 detik.

Mulai percobaan dengan TGS822, TGS2602, dan TGS816, lalu lakukan ablasi menambahkan TGS2611/MQ8/TGS2620 satu per satu. Gunakan validasi yang mengelompokkan seluruh satu CSV sebagai satu unit, serta pengujian independen pada **spesimen, sesi, dan perangkat yang benar-benar berbeda**, setelah metadata tersedia. Lima batch per roasting masih kecil untuk mengklaim akurasi generalisasi. Kategori kopi RAT/MUK/GAY hanya memiliki satu roasting pada dataset sekarang; jangan memasukkannya begitu saja ke evaluasi tiga-roasting lintas semua origin tanpa menangani ketidakseimbangan dan perancuan origin–roast.

## Protokol pengambilan ulang

1. Pastikan satu perangkat yang sama dan log `device_id`, tanggal/jam sebenarnya, nomor spesimen, operator, gram kopi, cara penggilingan, waktu sejak roasting, serta urutan pengambilan.
2. Jalankan kontrol blank/udara bersih sebelum sampel; periksa nilai baseline 10 sensor dan suhu/RH. Lakukan pembersihan/purging hingga baseline stabil **berdasarkan kriteria yang ditentukan dari data kontrol**, bukan semata perkiraan waktu.
3. Uji ulang kandidat prioritas tinggi setidaknya dua kali pada preparasi sampel terpisah bila memungkinkan; acak urutan Light/Medium/Dark dan gunakan periode stabilisasi yang konsisten.
4. Ulangi blank setelah tiap pengambilan guna mendeteksi carry-over/residu chamber. Bandingkan drift dalam 30 siklus terhadap kontrol blank dan kelompok referensi sehat.
5. Simpan uji ulang sebagai file **baru** dengan identitas run/batch unik, jangan overwrite CSV lama. Tautkan `retest_of`, device, dan alasan pemeriksaan pada ledger metadata.
6. Bandingkan ulang median respons per siklus, perubahan baseline, dan distribusi antar-recording; jika anomali masih terulang secara konsisten dalam kondisi terkontrol, jangan membuangnya sebagai outlier secara otomatis.
7. Untuk menghindari label confounding, lakukan validasi prospektif minimal 2–3 spesimen baru per roast pada origin prioritas (terutama TEM/GAW), disebar di beberapa sesi dan bila mungkin alat berbeda.

## Batas interpretasi dan keputusan

**Keputusan saat ini:** jangan memilih atau menghapus sensor berdasarkan satu ranking ini; **uji ulang 7 file prioritas tinggi terlebih dahulu**, tinjau 3 file prioritas bersyarat dan 2 identitas batch ganda, lalu evaluasi semua kelas dengan pengukuran terkontrol. Sisanya yang mendapat flag `PERLU_REVIEW` tidak wajib diambil ulang secara massal. Semua sumber tetap sah secara struktur sampai terdapat bukti gangguan dari pengujian kontrol.

Semua threshold robust z, variasi, dan drift di sini adalah indikator screening eksploratif (dengan jumlah batch per kelas hanya sekitar lima). Diagnosis *hardware drift*, pengaruh senyawa kopi yang sesungguhnya, dan validitas klasifikasi AI **belum dapat disimpulkan** tanpa metadata per perangkat serta eksperimen kontrol.

Detail replikasi numerik: `recording_retest_priority.csv`, `sensor_primary_batch_with_outlier_flags.csv`, `repeatability_per_origin_roast_sensor.csv`, `cycle_per_sensor.csv`, `sensor_exploratory_ranking.csv`, dan `drift_to_response_heatmap.png`.
