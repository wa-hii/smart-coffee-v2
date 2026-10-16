# Plug-and-play COM autodetection dan CSV Receiver untuk laptop Windows lain

**Tanggal:** 16 Oktober 2026. **Cakupan:** aplikasi penerima Python/Windows, installer auto-start, dan paket portable. **Tidak mengubah/flash firmware ATmega2560, HMI Nextion, EEPROM, data kopi, atau baseline lama.**

## Permasalahan, solusi, dan batas perangkat keras

Pengambilan data sebelumnya bergantung pada listener Windows yang mengunci COM5, dijalankan terpisah, dan data ditulis ke `data/raw` pada komputer penerima. Saat USB E-Nose dipindah ke laptop teman, nomor COM berbeda dan/atau listener belum terinstal/dijalankan, sehingga komputer tersebut tidak membuat CSV. **ATmega2560 tidak memiliki izin atau kemampuan menulis folder laptop lewat USB serial tanpa receiver yang berjalan.** Tidak ada backfill/replay jika pengambilan selesai sebelum PC terhubung. File CSV disusun dari sampel serial real-time, bukan dikirim sebagai file utuh dari flash mikrokontroler.

Perubahan `scripts/lcd_acquisition_service.py`:

- Default `--port auto` menggantikan default hardcoded `COM5`, dengan `--port COM5` tetap didukung untuk kontrol manual.
- `scripts/usb_autodetect.py` memilih satu-satunya port USB dengan VID:PID yang cocok: FT232R `0403:6001`, Mega2560 `2341:0042`/`2A03:0042`, CH340 `1A86:7523`, CP210x `10C4:EA60`. `--usb-serial` dapat mengunci adaptor tertentu. Jika 0 atau >1 port cocok, **fail closed**: menunggu atau meminta konfigurasi eksplisit, tidak mengambil port secara acak.
- Saat start tanpa perangkat, listener membuat `data/raw`, `.incoming`, `incomplete`, dan `data/baseline` pada root paket; status `waiting_for_device`. Bila adaptor muncul/COM berubah, listener scan ulang dan membuka 115200 bps secara pasif dengan DTR/RTS **False**. Tidak mengirim perintah START, tidak memicu pompa/valve.
- Jika koneksi putus selama pengambilan, partial CSV tetap di `data/raw/incomplete`, tidak dipromosikan sebagai final. Jika `ACQ_COMPLETE` dan QC 30 siklus lulus, CSV final masuk `data/raw`, menggunakan penamaan yang sudah dihasilkan dari LCD dan suffix saat bentrok agar file lama tidak tertimpa.
- Baseline menu Calibrate 60 sampel tetap tersimpan di `data/baseline/`; AI Test tidak masuk dataset berlabel; model AI tidak diubah.

## Penggunaan laptop kedua

`scripts/build_windows_receiver.py` membuat `dist/Smart_Coffee_ENose_USB_Receiver_Windows.zip` yang hanya berisi **16 file kode/dependency metadata**, bukan dataset atau file pribadi. Ekstrak ke folder tetap (misalnya Documents), pastikan Python 3.10+, driver USB FTDI/CH340, dan internet untuk pip. Jalankan **`windows_receiver/INSTALL_ON_THIS_LAPTOP.bat` sekali pada laptop tersebut**. Installer membuat `.venv`, memasang `pyserial`, `pandas`, `numpy`, membuat folder keluaran, memasang shortcut Windows Startup milik user, dan mencoba memulai listener sekarang. Pada login berikutnya listener mulai otomatis serta menunggu USB, sehingga colok USB kapan saja setelah login akan dideteksi. Tidak ada Windows autorun langsung oleh hardware USB.

Sebelum mulai Take Data dari Nextion, lihat status `logs/acquisition_service.status.json` **connected**, dan tutup program lain yang memakai COM. Penerima harus aktif sebelum event `ACQ_START`, bukan setelah akuisisi berjalan. Script deteksi read-only: `windows_receiver/TEST_PORT_DETECTION.bat`. Pencopotan shortcut lewat `REMOVE_AUTOSTART.bat` tidak menghapus data.

## Bukti QA offline dan keterbatasan

- `test_usb_autodetect.py` PASS: tanpa USB, pilihan FT232R COM5, switching COM5→COM7 setelah simulated disconnect, beberapa kandidat fail-closed, filter nomor seri, pembuatan folder, DTR/RTS tidak diaktifkan. **Tidak membuka serial fisik pada tes ini.**
- `test_receiver_bundle.py` PASS: ZIP dibuka dalam folder temporary, seluruh modul listener/dependency diimpor pada runtime host, bundle tidak memuat `data/raw` historis. Pemeriksaan syntax PowerShell installer PASS (tanpa menjalankan instalasi pada laptop orang lain).
- `test_acquisition_payload.py`, `test_acquisition_integrity.py`, `test_baseline_recording.py`, `test_take30_contract.py` PASS. `check_usb_receiver.py` read-only pada laptop pengembang menemukan COM5 FTDI `0403:6001`, USB serial `A10KMM3SA`.
- **Belum terbukti**: instalasi Python/driver di laptop teman, Windows startup pada akun berbeda, kualitas listrik USB semua hardware clone, serta E2E 30 siklus pertama di laptop teman. Semua butuh uji langsung di laptop tujuan. Deteksi VID:PID mengidentifikasi adaptor USB, **bukan verifikasi identitas firmware**; cek `FW_HELLO` bila tersedia dan jangan menganggap status connected sebagai PASS data sensor.

## Pengaruh terhadap mesin saat ini

Versi firmware `baseline60-r0safe-20261016` yang telah ter-flash pada ATmega **tidak perlu diflash ulang**: protokol JSON, USB baud 115200, Take Data 30×(25+5) dan baseline 60s sudah ada. Perubahan ini **hanya pada software komputer penerima**. Proses listener lama yang sedang running dengan argumen `--port COM5` tidak otomatis berubah perilakunya sebelum ia dijalankan ulang dengan `--port auto`. Restart hanya saat IDLE, tanpa file `.incoming` aktif.

## Verifikasi langsung di laptop developer (setelah QA dan commit awal)

- Diperiksa bahwa listener lama PID `9584` satu-satunya listener aktif, folder staging `data/raw/.incoming` dan `data/baseline/.incoming` kosong, log menyatakan sesi terakhir sudah COMPLETE, FT232R `0403:6001` pada COM5 tersedia.
- Listener lama dihentikan pada kondisi IDLE, lalu listener baru dimulai memakai `pythonw.exe scripts/lcd_acquisition_service.py --port auto --baud 115200`, PID **27576**.
- Log host pada **19:30:44 WIB** mencatat `USB detected -> COM5 (passive receive)` lalu `CONNECTED COM5`; status JSON menampilkan `state=connected`, `port=COM5`, `pid=27576`.
- **PASS:** auto-detect USB COM5 dan pembukaan port fisik secara pasif, tanpa manual setting dan tanpa memulai akuisisi, firmware upload, atau perintah aktuator. **NOT RUN:** uji pindah USB antar-port fisik, replay otomatis, file CSV 30 siklus pertama pada laptop kedua, maupun eksekusi installer pada laptop kedua.
- Startup shortcut baru tidak dipasang pada laptop developer oleh langkah verifikasi ini. Listener auto sekarang berjalan dalam sesi Windows aktif; bila ingin otomatis setelah login ulang, jalankan installer pada laptop tujuan.
