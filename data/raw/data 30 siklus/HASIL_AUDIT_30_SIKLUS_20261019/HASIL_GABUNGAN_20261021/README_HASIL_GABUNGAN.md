# Audit dan merge data 30 siklus — 21 Oktober 2026

Sumber asli **tetap utuh**; folder audit sebelumnya juga tidak diubah.

- CSV arsip lama: **69**
- CSV baru diperiksa: **83**
- Baru lolos struktur: **75**
- Baru gagal struktur: **8**
- Baru valid unik masuk pool: **73**
- Baru incomplete unik: **3**
- Baru duplikat disisihkan: **7**
- **Total dataset valid unik gabungan: 111**
- **Total data incomplete/anomali unik: 34**

## Struktur
- `01_VALID_GABUNGAN/`: data old valid dan new valid unik (tidak overwrite).
- `02_INCOMPLETE_DAN_ANOMALI/OLD/`: data lama yang gagal audit, dikelompokkan berdasarkan kategori.
- `02_INCOMPLETE_DAN_ANOMALI/NEW/`: data baru gagal audit yang belum ada sebelumnya.
- `03_DUPLIKAT_BARU_TIDAK_DIGABUNG/`: seluruh CSV baru identik dengan sumber lain, tidak dihitung dua kali.
- `AUDIT_NEW_PER_FILE.csv`: semua 83 CSV baru, alasan per file dan tindakan merge.
- `INCOMPLETE_KETIDAKSESUAIAN.csv`: daftar seluruh data tidak valid baru dan lama, termasuk duplikat yang dikeluarkan.
- `AUDIT_PEMENUHAN_5X_PER_KOPI.csv`: progres target pengambilan valid per kombinasi.
- `MANIFEST_GABUNGAN.json`: catatan lengkap referensi source, hash, serta duplikasi.

## Kaidah data
- Tepat 900 baris valid, indeks urut 1..25 purging dan 1..5 collecting untuk setiap siklus.
- 30 siklus lengkap, timestamp naik dan sekitar 1 Hz; tidak ada ADC hilang/out of range.
- Nama file mesti sesuai `sample_id`, `batch_id` serta roast. File berlabel incomplete tidak pernah otomatis diloloskan.
- Duplikasi tidak dibedakan hanya dari nama; isi berkas SHA256 dan fingerprint 16 kolom sensor-waktu diperiksa.
- File yang sama dengan arsip invalid karena nama batch salah boleh masuk sebagai *versi metadata valid*, sedangkan arsip invalid tetap dikarantina.
- Semua data original dan arsip audit 19 Oktober tetap di lokasi sebelumnya.
- Data identik tidak diulang dalam folder valid, dan bentrok nama dengan isi berbeda diberi sufiks `__NEW_hash`.

## Bentrokan nama berbeda isi
- `M-GRB_B60.csv` -> `M-GRB_B60__NEW_9645c0fc1e.csv`
