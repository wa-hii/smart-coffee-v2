# Fix HMI yang aktif: Invalid Page ID pDataRun pada pTake Start

**Tanggal:** 16 Oktober 2026. **Jenis perubahan:** perbaikan kode event HMI, **bukan perubahan visual**. File yang diubah: `nextion/NX4827T043_011/project/RoastSense_NX4827T043_011.HMI` (bukan file `...COMPILE_READY.HMI` dari asumsi 12 halaman yang terbukti tidak sesuai screenshot operator).

## Bukti dan perbaikan

- Screenshot dari Nextion Editor pengguna memperlihatkan **11 halaman aktif** dan tidak memiliki `pDataRun`: `pSplash`, `pHome`, `pTake`, `pDataDone`, `pTest`, `pTestRun`, `pResult`, `pCal`, `pSettings`, `pHistory`, `pAlert`.
- Pada HMI hasil Save pengguna pukul 20:03 WIB, page `pTake` memiliki event tombol `mStart` dengan instruksi `prints "EVT:DATA_START",0`, `printh 0D 0A`, lalu **`page pDataRun`**, penyebab paling spesifik yang ditemukan untuk error `Invalid Page ID:pDataRun`.
- Instruksi navigasi yang salah diganti dengan **`doevents`** (disimpan dalam slot 13 byte yang sama, menggunakan padding spasi). Pengiriman `EVT:DATA_START` dan terminator CRLF **dipertahankan**. Setelah menekan START, firmware versi 11 halaman yang dipersiapkan pada commit `2a7c3f7` akan tetap menampilkan `pTake` selama pengambilan data dan membuka `pDataDone` setelah selesai.
- Pada file hasil Save, entri directory `2.pa` masih menunjuk ke salinan stale yang checksum-nya gagal. Entry primer dan backup diperbaiki agar menunjuk ke blob `pTake` valid di offset `15220268` sepanjang 8115 byte, dan checksum directory dihitung ulang. Tidak menghapus atau menambah halaman, tidak mengubah resource gambar/font, warna, maupun komponen lain.
- **Sebanyak 34 byte berubah** pada file 15 MB; ukuran HMI tetap. SHA256 sebelum: `9729ea9621299fc89915eeabc26660f78c1e6c3edb9e3eb1555ae6cd267a4967`. SHA256 sesudah: `86d809e8eb90a74a9b9e6115ae16e310f060f8972aa73a23c918bb49605b3bd5`.
- Backup byte-identical disimpan lokal (ignored dari Git) di `results/hmi-repair-backup-20261016/ROOT_HMI_BEFORE_11PAGE_NAV_FIX_9729ea962129.HMI`.

## QA dan batas

- `python nextion/NX4827T043_011/tools/verify_11page_start_navigation.py`: **PASS**. Memeriksa direktori primer/backup, CRC `pTake`, event `EVT:DATA_START`, tidak ada lagi referensi `page pDataRun` pada biner yang diedit, komponen lain sama persis, seluruh resource lain unchanged.
- **Belum diverifikasi melalui tombol Compile resmi Nextion Editor.** Tes checksum biner bukan pengganti kompilasi. Jangan upload TFT apabila Nextion Editor masih error.
- HMI ini merupakan versi dengan 11 komponen `pTake`; firmware `take11-baseline60-20261016` yang disiapkan terpisah memerlukan elemen status `tStat` dan hotspot tambahan yang ada pada versi HMI lain. Sebelum digunakan di alat fisik, lakukan **sinkronisasi lengkap komponen HMI 11 halaman dengan firmware**, uji offline, lalu flash dengan izin operator. Penyelesaian error satu baris tidak boleh diklaim sebagai QA ujung-ke-ujung.
- Tidak mem-flash ATmega2560, tidak meng-upload TFT, tidak membuka COM5, dan tidak memodifikasi dataset, backup baseline, atau pengaturan lokal `platformio.ini` pada pekerjaan ini.

## Cara mencoba

Buka **`RoastSense_NX4827T043_011.HMI`** (file yang diperbaiki, bukan `RoastSense_NX4827T043_011_COMPILE_READY.HMI`), lalu klik **Compile**. Jika ada error berikutnya, kirim log terbaru untuk audit lanjutan tanpa menghapus warna/layout yang telah disimpan.
