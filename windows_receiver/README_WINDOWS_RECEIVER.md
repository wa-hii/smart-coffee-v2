# Smart Coffee E-Nose USB receiver otomatis (Windows)

## Mengapa di laptop teman belum ada CSV?

ATmega2560 mengirim sampel real-time melalui USB serial **ketika operator menekan Take Data**. Firmware tidak bisa membuat folder/data di laptop tanpa aplikasi penerima. Tidak ada penyimpanan internal untuk mengambil ulang sesi lama setelah USB dicabut. Laptop lain memerlukan driver USB yang sesuai, Python 3.10+, dan receiver ini yang berjalan **sebelum** menekan tombol Start.

## Instal sekali pada setiap laptop

1. Ekstrak **`Smart_Coffee_ENose_USB_Receiver_Windows_v3_Timing900.zip`** ke lokasi yang boleh ditulisi, misalnya `Documents\SmartCoffee_Receiver`. Jangan pindahkan folder setelah instalasi. Hindari `Program Files` dan folder ZIP yang belum diekstrak. Ini paket terbaru yang menyertakan pemeriksaan timing 900 detik firmware `take12-abs900-no-uiwait-20261017`.
2. Instal **Python 3.10+ 64-bit** untuk Windows; saat setup diperlukan internet untuk menginstal `pyserial`, `pandas`, dan `numpy`. USB FT232R memerlukan driver agar muncul sebagai COM di Device Manager.
3. Klik dua kali `windows_receiver\INSTALL_ON_THIS_LAPTOP.bat`. Proses ini membuat `.venv`, menginstal dependency, **menjalankan preflight Windows tanpa mengakses COM**, membuat folder `data/raw` dan `data/baseline`, memasang shortcut pada Startup pengguna, dan memulai receiver. Tidak membutuhkan admin untuk shortcut Startup.
4. Hubungkan USB E-Nose. Listener yang berjalan mencari COM yang cocok secara otomatis, termasuk setelah USB dicabut/dicolok dan nomor COM berubah (misalnya COM5 menjadi COM7).
5. Pastikan `logs/acquisition_service.status.json` mencatat `connected`, lalu tekan **Take Data** pada Nextion. Setelah sekitar 15 menit dan `ACQ_COMPLETE` valid, file masuk `data/raw/D-GAW_BNN.csv` sesuai pilihan LCD. Saat **Calibrate → Start Calibration**, file masuk ke `data/baseline/`.

   Receiver v3 memeriksa `elapsed_active_ms`, `target_active_ms`, dan `paused_ms` jika dikirim firmware baru. Durasi aktif harus berada dalam toleransi kurang dari 1 detik terhadap target 900 detik. Sesi yang gagal QA tidak diterbitkan sebagai CSV final; data mentahnya disimpan di `data/raw/incomplete/`. Jika perangkat sengaja di-Pause, hanya waktu **aktif** yang dibandingkan terhadap 900 detik.

## Diagnostik dan perlindungan data

- `windows_receiver\TEST_PORT_DETECTION.bat` menampilkan daftar port COM dan hasil deteksi otomatis, **tanpa membuka port atau mengirim perintah**.
- **Windows 10 error:** jalankan `windows_receiver\DIAGNOSE_WINDOWS_10.bat`, lalu kirim screenshot seluruh baris ERROR. Pemeriksaan ini menunjukkan versi/arsitektur Python, dependency, izin folder, dan adaptor COM; tidak mengakses firmware. Jika ingin melihat error service secara langsung, jalankan `windows_receiver\START_RECEIVER_DEBUG.bat` (jangan mulai akuisisi saat mengganti listener). Jika muncul `lcd_acquisition_service sudah berjalan`, receiver lain sudah aktif: periksa `logs/acquisition_service.status.json` atau jalankan Task Manager. Jangan menghentikan proses ketika akuisisi masih berlangsung.
- Jika installer gagal di tahap `pip install`, periksa apakah Python 64-bit tersedia, internet aktif, versi Python memenuhi syarat, dan apakah proxy/firewall Windows memblokir PyPI. Jika folder berada di lokasi yang tidak dapat ditulis, ekstrak ke Documents.
- `waiting_for_device` artinya USB belum ditemukan atau terdapat beberapa perangkat yang cocok; `connected` artinya COM berhasil dibuka, **bukan bukti firmware atau kalibrasi sudah benar**; `waiting_for_port` artinya COM gagal dibuka atau dipakai aplikasi lain. Periksa `logs/acquisition_service.log`.
- Auto-detect mendukung FT232R `0403:6001` (PCB custom), Arduino Mega2560 `2341:0042`/`2A03:0042`, CH340 `1A86:7523`, dan CP210x `10C4:EA60`. Bila ada beberapa port cocok sekaligus, receiver **tidak memilih secara acak**. Tutup listener yang berjalan saat IDLE dan jalankan eksplisit: `.venv\Scripts\python.exe scripts\lcd_acquisition_service.py --port COM7` atau `--port auto --usb-serial SERIAL_USB`.
- Jangan membuka Arduino/PlatformIO Serial Monitor bersamaan; COM hanya bisa digunakan satu aplikasi pada suatu waktu.
- Jika USB terputus di tengah 30 siklus, partial CSV masuk `data/raw/incomplete/`, **bukan** diterbitkan sebagai CSV final. Tidak ada backfill data yang terlewat setelah tersambung kembali.
- File dengan nama sama **tidak ditimpa**: digunakan suffix timestamp. Folder `data/raw` dibuat otomatis walau kosong di laptop baru.
- Auto-start berjalan setiap **login Windows**. USB dicolok saat login aktif akan ditemukan karena listener tetap memindai port. Windows tidak otomatis menjalankan aplikasi atau menyalin data dari mikrokontroler hanya karena USB terpasang jika receiver belum diinstal/dijalankan.
- `windows_receiver\REMOVE_AUTOSTART.bat` menghapus shortcut autostart; tidak menghapus CSV dan tidak menghentikan listener yang sudah berjalan.

## Jalankan manual (mis. untuk debug)

Setelah installer selesai dan receiver latar belakang sudah dihentikan pada kondisi IDLE:

```powershell
.venv\Scripts\python.exe scripts\lcd_acquisition_service.py --port auto --baud 115200 --verbose
```

Tiap sesi kopi harus benar-benar diawali event `ACQ_START` dari Nextion **setelah** penerima terhubung. Pindah USB ketika sesi aktif mengakibatkan sesi tersebut tidak lengkap. Program tidak mengaktifkan valve/aktuator, tidak melakukan flashing, tidak menulis EEPROM, dan AI tetap tidak dipromosikan.
