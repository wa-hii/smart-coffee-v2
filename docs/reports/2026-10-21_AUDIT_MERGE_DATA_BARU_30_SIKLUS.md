# Audit & merge 83 CSV baru E-Nose dengan arsip 30 siklus — 21 Okt 2026

## Sumber dan lokasi hasil

- Sumber baru: `data/raw/new/` — 83 CSV, seluruhnya diperiksa.
- Arsip lama: `data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019/` — 69 CSV telah diaudit.
- Hasil baru **tanpa menimpa sumber**: `data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019/HASIL_GABUNGAN_20261021/`.

## Kriteria diterima

- Format kolom canonical sama; metadata sample ID, batch ID, origin dan roast konsisten dengan filename.
- 30 siklus lengkap dan tepat 900 sampel valid per CSV.
- Tiap siklus 25 sampel purging dan 5 sampel collecting, indeks runtut.
- Timestamp monoton meningkat; sampling mendekati 1 detik; waktu total sekitar 900 detik.
- Semua 10 ADC integer valid tanpa missing; suhu/kelembapan di luar rentang fisik ditandai.
- Hash byte dan fingerprint time-series sensor (tanpa metadata label) diperiksa untuk mencegah duplikasi, termasuk file dengan nama berbeda.
- Versi metadata yang dibetulkan dapat menggantikan **copy arsip yang invalid**, tetapi copy invalid tetap disimpan untuk provenance.

## Hasil

| Kategori | Jumlah |
|---|---:|
| Data lama, seluruh CSV | 69 |
| Data baru, seluruh CSV | 83 |
| Data baru lolos struktur | 75 |
| Data baru gagal struktur | 8 |
| Data baru valid unik masuk gabungan | 73 |
| Data baru incomplete unik masuk karantina | 3 |
| Data baru duplikat (valid ataupun invalid) tidak dihitung ulang | 7 |
| **Total valid unik gabungan** | **111** |
| Total incomplete/anomali unik dikarantina | 34 |

## Delapan CSV baru tidak lengkap

| Nama file (disederhanakan) | Sampel | Kekurangan dari 900 | Status duplikasi |
|---|---:|---:|---|
| L-CAT B64 INCOMPLETE | 897 | 3 | identik dengan arsip incomplete lama |
| L-MING B61 INCOMPLETE | 899 | 1 | identik dengan arsip incomplete lama |
| L-TOR B67 INCOMPLETE | 899 | 1 | incomplete baru unik |
| M-CAT B66 INCOMPLETE (akhiran `...e6b06`) | 899 | 1 | incomplete baru unik |
| M-CAT B66 INCOMPLETE (akhiran `...e6b07`) | 899 | 1 | identik dengan M-CAT B66 `...e6b06` |
| M-GRB B62 INCOMPLETE (akhiran `...54466`) | 899 | 1 | identik dengan arsip incomplete lama |
| M-GRB B62 INCOMPLETE (akhiran `...54467`) | 899 | 1 | identik dengan arsip incomplete lama |
| M-MING B60 INCOMPLETE | 888 | 12 | incomplete baru unik |

Semua file incomplete baru memiliki anomali hitungan / indeks fase 25:5,
dan beberapa menunjukkan selang waktu sensor yang lebih dari satu detik.
Tidak ada yang diluluskan dengan interpolasi, padding, atau duplikasi baris.

## Data duplikat dan bentrokan nama

- `L-CAT_B63.csv` dan `L-MING_B60.csv` identik dengan file VALID lama; keduanya tidak ditambahkan ulang.
- `M-GRB_B60.csv` dari folder baru **identik** dengan arsip lama `M-GRB_B67.csv` yang berstatus METADATA salah (isi arsip sebenarnya M-GRB B60). File baru diterima karena sudah sesuai label; arsip salah tetap dikeluarkan.
- Data valid lama `M-GRB_B60.csv` memiliki isi **berbeda** dari `M-GRB_B60.csv` baru; keduanya dipertahankan. Versi baru diberi nama `M-GRB_B60__NEW_9645c0fc1e.csv` di folder gabungan tanpa mengubah metadata internal.
- Data yang cocok secara signal/time-series atau hash penuh dianggap duplikat, bukan tambahan sampel independen.

## Pemenuhan target penelitian

Target: 21 kombinasi origin-roast × 5 pengambilan = 105 dataset.
Setelah merge, hanya `MING / medium` yang masih **4/5**, sehingga memerlukan
**1 tambahan pengambilan valid**. Beberapa kombinasi sudah memiliki lebih
dari 5 file; jumlah total unik 111 tidak berarti seluruh kelas sudah merata.
Sesi berbeda dan identitas alat fisik belum dapat disimpulkan hanya dari CSV.
Rincian: `AUDIT_PEMENUHAN_5X_PER_KOPI.csv`.

## QA dan batasan

- PASS pemeriksaan hash seluruh input dan seluruh salinan (tidak ada file overwrite).
- PASS audit ulang **111 file valid gabungan**; semuanya memenuhi kontrak 30 siklus 25 purging/5 collecting.
- PASS test synthetic `test_merge_new_30_siklus_audit.py`: metadata corrected copy, bentrokan filename, duplicate valid dan incomplete, dan penolakan overwrite.
- PASS `test_audit_dataset_30_siklus.py`.
- Source new dan manifest old dibiarkan utuh; tidak mengubah alat, firmware, atau COM.
- Validitas pengukuran kimia, kebocoran data model, dan independensi batch/alat masih perlu QA tersendiri sebelum training.

## Reproduksi

Perintah `python scripts/merge_new_30_siklus_audit.py` menghasilkan folder
gabungan baru dan **sengaja menolak overwrite** output yang sudah ada.
Untuk audit ulang, gunakan lokasi baru (ubah `OUTPUT`) tanpa menimpa hasil
yang sudah terdokumentasi.
