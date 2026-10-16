# Perbaikan Invalid Page ID:pDataRun setelah edit warna di Nextion Editor

## Diagnosis aktual

- HMI aktif: `nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI` yang terakhir disimpan manual lewat Nextion Editor.
- Error compiler pengguna: `Invalid Page ID:pDataRun` setelah kompilasi melewati halaman pSplash, pHome, pTake. Penggunaan memori yang tercetak bukan error.
- Audit biner pertama menemukan **entri `3.pa` tidak ada** di directory HMI terbaru, meskipun 11 page lain valid, CRC seluruhnya cocok, dan kedua directory checksum primer/backup konsisten. `pDataRun` masih tersimpan sebagai dua blob CRC valid di file lokal. Dengan demikian error konsisten dengan page directory yang kehilangan referensi, bukan karena warna atau kapasitas memori.
- Blob `pDataRun` terbaru di file yang sama ada pada offset `15297761` ukuran `9141`, memuat 11 komponen dan event Pause/Cancel. Dipilih untuk mempertahankan perubahan manual terbaru (bukan mengembalikan seluruh HMI ke versi Git lama).

## Perbaikan aman

1. Backup byte-identical **sebelum setiap perubahan** disimpan lokal di folder ignored `results/hmi-repair-backup-20261016/`:
   - `ORIGINAL_3c771322159b.HMI` — kondisi terakhir yang masih error (SHA-256 diawali `3c771322159b`).
   - `PAGE3_RESTORED_625eab48f2aa.HMI` — kondisi setelah direktori 3.pa dipulihkan, sebelum koreksi jCycle (SHA-256 diawali `625eab48f2aa`).
2. `repair_missing_page3_directory.py` menambah record `3.pa` pada tabel directory primer dan backup, menggunakan blob pDataRun paling baru di file existing. Checksum directory keduanya dihitung ulang. Semua image, font, page lain, serta byte resource asli dipertahankan.
3. QA menyeluruh kemudian menemukan `jCycle` pada page pDataRun terbaru bertipe **Text** walaupun firmware menyetelnya sebagai Progress `.val`; di HMI Git HEAD komponen tersebut bertipe Progress. `restore_jcycle_progress_type.py` merekonstruksi **hanya record komponen jCycle** dari Progress yang valid, mempertahankan ID, koordinat, ukuran, nilai warna bco/pco dari edit pengguna, serta seluruh record komponen lainnya di page tersebut. Blob page yang dikoreksi ditambahkan; directory `3.pa` diarahkan ke blob terbaru. Sebelas page lain byte-identical.
4. HMI final: SHA-256 `b02e7c495c915c8a706dc50bb30fe575874d3b8c4fcfa9c3f8f10e86ec3bd4b2`. File ini mengandung perubahan warna/layout pengguna, bukan snapshot lama.

## Bukti QA

- 12/12 halaman bernama benar dengan CRC valid; direktori primer dan backup konsisten, checksum valid.
- Nextion model `NX4827T043_011`, model CRC `0xca296eb1`.
- `python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py`: **PASS** untuk 12 aset, 12 page, 23 event, handler firmware, USART2 @ 9600, `jCycle` bertipe Progress, `tTemp` dan `tHum` bertipe Text.
- Tidak ada firmware upload, LCD TFT flashing, perubahan data sensor, atau aksi fisik selama perbaikan.

**Batas penting:** Nextion Editor GUI compile **belum diverifikasi otomatis** pada pekerjaan ini. Pengguna perlu membuka file canonical yang sudah diperbaiki di Nextion Editor dan menekan Compile. Jika masih muncul error, simpan log baru lalu hentikan proses upload TFT sampai masalah teratasi. Backup asli tersedia untuk rollback. Tidak perlu mengubah firmware ATmega hanya untuk error HMI ini.
