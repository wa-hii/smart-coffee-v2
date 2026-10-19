# Windows multi-device receiver COM5/6/7 — QA 19 Oktober 2026

## Scope dan perubahan

Satu laptop Windows menjalankan satu proses supervisor dan tiga proses
receiver yang terpisah. Mapping awal `COM5=ALAT_1`, `COM6=ALAT_2`,
`COM7=ALAT_3` diperiksa read-only dari USB VID/PID sebelum port dibuka.
Jika adaptor memiliki USB serial number unik, receiver kemudian memilih
secara otomatis berdasarkan serial tersebut, sehingga perubahan nomor COM
tidak menyebabkan identitas alat tertukar. Tanpa USB serial, proses memakai
port COM statis dan operator wajib verifikasi ulang setelah koneksi berubah.

Tiap alat memiliki CSV, incomplete, baseline, log, dan status sendiri:
`data/raw/devices/ALAT_N/`, `data/baseline/devices/ALAT_N/`,
`logs/devices/ALAT_N/`. Nama sampel/batch asli dari firmware tetap dijaga;
duplikasi antar perangkat tidak saling overwrite. Sesi hanya diterbitkan
sebagai CSV final setelah `ACQ_COMPLETE` dan validasi 30 siklus lulus.

Supervisor menahan lock dan named mutex yang sama dengan receiver v4
single-device sehingga tidak dapat menjalankan dua receiver v4 bersamaan.
Receiver lebih lama tidak menggunakan mutex: sebelum `--start`, supervisor
memeriksa proses single-device lama dan menolak bila ada yang masih hidup.
Tidak ada serial open jika `--start` tidak diberikan. Tidak ada flash,
perintah START, EEPROM, atau aktuator yang diakses.

## Pengujian

| Check | Hasil |
|---|---|
| 3 proses paralel sintetis | PASS |
| Setiap alat 900 baris/30 siklus | PASS |
| Ketiga alat dengan nama sampel/batch sama | PASS, 3 file terpisah |
| Validasi VID/PID, port duplicate, missing, USB serial duplicate | PASS |
| Fail-closed saat receiver lama masih aktif | PASS (mock) |
| `--start` absen tidak membuka serial | PASS (mock, dan hanya preflight) |
| Receiver v4 singleton regression | PASS |
| USB autodetect regression | PASS |
| Akuisisi integrity regression | PASS |
| Take30 timing contract + absolute timing | PASS |
| Paket ZIP v5 ekstraksi/import/preflight | PASS |

**Batas pemeriksaan:** host DevSpace saat ini tidak melihat COM5/6/7 dan
melaporkan `PREFLIGHT FAIL: COM5 not found` sesuai fail-closed. Laptop lama
pengguna yang memiliki COM5/6/7 belum diuji langsung; 3 USB serial fisik,
proses penerimaan simultan 15 menit, dan hash CSV fisik perlu diverifikasi
secara prospektif setelah receiver lama dimatikan ketika IDLE.

`scripts/test_acquisition_suite.py` (suite historis yang memvalidasi CSV
di `data/raw/*.csv` sebagai *5 siklus*) tidak PASS untuk dataset 30 siklus
B41+ dan juga menemui encoding console Windows cp1252 pada pesan error.
Ini keterbatasan suite historis, **bukan** klaim kegagalan uji
`scripts/test_multi_device_receiver.py` yang khusus mengecek 30 siklus.
Tidak ada CSV milik pengguna yang dihapus/ditulis ulang pada pekerjaan ini.
