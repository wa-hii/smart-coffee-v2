# Import B36/B37 dari branch irul — raw evidence, belum approved ML

**Sumber:** `origin/irul` commit `f51a0d436656e9279dc96bd2c71500c1b6bc8fa4`, direktori `data/`.
**Tujuan:** `data/raw/irul_B36_B37/` pada branch `wahyu`.

Tersalin **32 CSV lengkap secara byte-for-byte**, terdiri atas **21 B36** dan **11 B37**; dua di antaranya adalah `BASELINE_B36.csv` dan `BASELINE_B37.csv`. Masing-masing SHA256 hasil salinan diverifikasi cocok dengan manifest hasil pembacaan Git. Bukti nama, SHA, ukuran dan commit sumber disimpan pada `data/analysis/irul_B36_B37_import_manifest.csv`.

**Tidak ada overwrite:** dua nama file `L-MING_B37.csv` dan `M-MING_B37.csv` sudah ada pada root `data/raw/` sebagai file lokal untracked; kedua hash berbeda dari versi `irul`. Karena itu seluruh berkas baru dipisahkan dalam subfolder import, dan data lokal tidak diubah.

**QA schema awal:** validator canonical pada CSV impor menghasilkan **27/32 PASS, 5/32 HOLD**. Yang HOLD karena `sample_idx` fase tidak kontigu: `D-CAT_B36.csv`, `D-GAW_B36.csv`, `D-GRB_B36.csv`, `D-MING_B36.csv`, `L-TOR_B36.csv`. Data ini tidak diperbaiki atau dihapus otomatis. `BASELINE` adalah sampel kontrol, bukan kelas roasting kopi. Status seluruh import tetap `HOLD_PROVENANCE_UNVERIFIED_NOT_BLIND` sampai identitas lot/spesimen, kondisi bench, label serta sesi benar-benar diverifikasi.

**Tidak menjalankan G3 atau flashing RC2.** Jangan otomatis menggabungkan B36/B37 dengan snapshot training B32–B35 dan jangan menyatakan hasilnya *independent prospective blind test*: batch tersebut sudah berada di branch `irul`, dan tidak ada bukti bahwa spesimennya baru serta bahwa model/threshold belum dipilih berdasarkan informasinya.
