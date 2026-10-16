# Koreksi desain aktif: hanya 11 halaman, pDataRun tidak digunakan

**Sumber kebenaran:** screenshot daftar Page dari Nextion Editor yang diberikan operator pada 16 Oktober 2026. Daftar sebenarnya: `0 pSplash`, `1 pHome`, `2 pTake`, `3 pDataDone`, `4 pTest`, `5 pTestRun`, `6 pResult`, `7 pCal`, `8 pSettings`, `9 pHistory`, `10 pAlert`.

## Akar masalah

Error Nextion `Invalid Page ID:pDataRun` masuk akal karena file HMI yang sedang **terbuka** di editor sudah tidak mempunyai halaman `pDataRun` dalam daftar GUI, tetapi referensi lama ke `page pDataRun` masih terdapat pada kode Touch Release / navigasi. Versi kerja lain di folder project dan spesifikasi lama masih mempunyai 12 halaman, sehingga jangan menganggapnya daftar halaman yang benar pada desain pengguna. Perbaikan sebelumnya yang mengembalikan 3.pa pada file `COMPILE_READY.HMI` didasarkan pada asumsi 12 halaman; asumsi tersebut dibatalkan oleh operator.

## Yang harus dilakukan di Nextion Editor

1. **Pastikan menyunting HMI yang benar**, dengan 11 halaman sesuai screenshot. Simpan salinan via File > Save As terlebih dahulu.
2. Klik dua kali pesan `Invalid Page ID:pDataRun` untuk masuk ke baris referensinya. Biasanya pada `pTake > mStart > Touch Release` terdapat `page pDataRun` dari versi lama; **hapus baris `page pDataRun` saja**, jangan hapus pengiriman event `prints "EVT:DATA_START",0` dan `printh 0D 0A`.
3. Periksa global/page event lain dengan referensi `page pDataRun`; hapus referensi ke halaman yang tidak ada. Jangan mengganti menjadi `page pDataDone` karena halaman itu khusus akuisisi selesai. Firmware versi 11 halaman menampilkan status run di `pTake` dan berpindah otomatis ke `pDataDone` setelah 30 siklus.
4. Compile ulang. Catat apakah `Compile Successful`. Jangan upload TFT atau flash firmware sampai compiler resmi PASS dan alur pTake/tDone diuji.

## Perubahan di firmware, belum di-flash

Pada `src/main.cpp`: navigasi pengambilan label aktif tetap di `pTake`; teks `tStat` menunjukkan fase (purging/collecting/paused), nomor siklus dan hitung mundur; selama aktif tombol START dan selector label dikunci, sedangkan tombol Back/Home yang memang ada menghentikan sesi. Setelah `ACQ_COMPLETE`, pindah ke `pDataDone`. Referensi firmware ke `pDataRun` dan `pDataRun.tSensors` dibuang. Take Data tetap 30 × (25 s purging + 5 s collecting), AI TEST tetap 5 siklus, baseline ADC tetap 60 sampel. Build PlatformIO serta test offline berhasil.

**Batasan UI:** karena desain 11 halaman tidak memiliki `mPause`/`mCancel` halaman Run, tombol Pause khusus dari desain lama belum tersedia. Back/Home menghentikan pengambilan seperti semula; pemetaan kontrol Pause memerlukan persetujuan pada elemen halaman `pTake`. Tidak ada aktuasi/hardware upload pada pekerjaan ini.

**HMI saat audit:** Nextion Editor masih berjalan dan mengunci file `COMPILE_READY.HMI`. Berkas `RoastSense_NX4827T043_011.HMI` dan `RoastSense_UI_FIX_QA.HMI` juga memiliki modifikasi lokal yang berbeda. Karena itu tidak aman mengubah biner HMI saat ini tanpa memastikan file aktif dan menyimpannya/tutup editor lebih dulu. Jangan menyamakan hasil build firmware offline dengan compile Nextion Editor.
