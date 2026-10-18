# Audit receiver ganda, pemulihan CSV, dan perbaikan Startup Windows — 18 Oktober 2026

## Ringkasan masalah

Operator melaporkan dua alat dapat menyelesaikan Take Data 30 siklus di LCD
tetapi CSV tidak tampak di `data/raw` repository. Audit DevSpace Windows
read-only menemukan **COM4 FT232R 0403:6001** tersedia; root repository
memiliki receiver `--port COM5` yang gagal karena `FileNotFoundError`.
Portable receiver v3 dari folder instalasi lain mencoba COM4 tetapi mendapat
`PermissionError(13, Access is denied)`. Portable receiver lama yang masih
berjalan justru memegang COM4 dan menyimpan ke folder `data/raw` **di dalam
folder portable tersebut**. Lima proses Python merepresentasikan tiga root
instalasi, termasuk proses launcher/interpreter Windows virtualenv.

## Bukti data dan pemulihan

Receiver portable lama mencatat:

| Selesai WIB | File | Sampel sensor | Validator |
|---|---|---:|---|
| 17:49 | `L-MING_B50.csv` | 900 | PASS |
| 18:35 | `L-MING_B50_20261018_182003.csv` | 900 | PASS |
| 19:05 | `L-MING_B50_20261018_185040.csv` | 900 | PASS |

Ketiga CSV disalin dari `Downloads/Smart_Coffee_ENose_USB_Receiver_Windows/
SmartCoffee_Receiver/data/raw` ke `data/raw/` checkout repo memakai
`scripts/recover_receiver_completed_csv.py --apply`. Validator menerima
30 siklus, 0 alasan gagal, SHA256 sumber dan hasil identik. Original
dipertahankan. Setelah re-run utilitas, hasil `identical_skipped=3`,
`copied=[]` (idempotent). Tidak menyentuh partial/incomplete, data asal,
USB serial, HMI, firmware, EEPROM, ataupun aktuator.

## Perbaikan dan batas runtime

- `scripts/lcd_acquisition_service.py`: status JSON kini menampilkan path
  absolut `receiver_root` dan `data_raw_dir` supaya lokasi simpan jelas.
  Named mutex Windows session-local mencegah **receiver baru berbasis v4**
  berjalan bersamaan dari beberapa folder. *Legacy receiver* lama yang tidak
  memiliki mutex tetap perlu dibereskan secara terarah saat alat IDLE.
- `windows_receiver/DIAGNOSE_ACTIVE_RECEIVERS.ps1` dan `.bat`: audit seluruh
  proses penerima, status, folder save, dan startup shortcut; tidak membuka COM.
- `windows_receiver/install_autostart.ps1`: jika ada receiver hidup, hanya
  memasang shortcut tanpa memulai listener pesaing.
- `windows_receiver/REPAIR_PROJECT_STARTUP.ps1`: script default dry run,
  saat `-Apply` membuat backup kedua shortcut lama, menghapus shortcut
  `Acquisition.lnk` dari Startup, dan mengarahkan satu `Receiver.lnk` ke
  interpreter host dan script repo `--port auto`. Verifikasi shortcut setelah
  perubahan PASS. Backup di `results/startup_receiver_backup_20261018/`.
  **Tidak menghentikan receiver berjalan**, sehingga efek pada akuisisi baru
  baru berlaku setelah migrasi runtime/login berikutnya.
- `scripts/build_windows_receiver.py` membangun ZIP baru
  `dist/Smart_Coffee_ENose_USB_Receiver_Windows_v4_SingleInstance.zip`.
  ZIP v3 tidak ditimpa; file CSV tidak termasuk ZIP.

## Quality gates

- PASS: `scripts/test_receiver_host_instance_lock.py` (Windows host mutex).
- PASS: `scripts/test_recover_receiver_completed_csv.py` (dry-run, no-clobber,
  collision, idempotent, invalid CSV rejection).
- PASS: `scripts/test_receiver_bundle.py` (ZIP v4 ekstraksi + imports + preflight).
- PASS: `scripts/test_usb_autodetect.py`.
- PASS: `scripts/test_acquisition_integrity.py`.
- PASS: `scripts/test_take30_contract.py`.
- PASS: `scripts/test_absolute_timing_firmware.py`.
- PASS: `git diff --check` (peringatan LF/CRLF Windows bukan error).
- **NOT RUN:** uji 30 siklus fisik baru, membuka COM4, flash, HMI, aktuator.

## Outstanding

1. Receiver live lama belum dihentikan supaya tidak memutus sesi yang mungkin
   sedang berlangsung. Saat semua alat dikonfirmasi IDLE, operator harus
   menutup receiver yang lama, lalu memulai satu receiver project `--port auto`
   dan memverifikasi status `connected` sebelum Take Data berikutnya.
2. Perlu satu run prospektif 30 siklus untuk memastikan file otomatis masuk
   ke **repo** dengan data lengkap dan event durasi aktif 900 detik.
3. Laptop Windows 10 ProBook yang hanya melihat COM Bluetooth mungkin masih
   gagal mengenali FT232R. Itu masalah terpisah (driver/USB/Device Manager)
   yang belum bisa diverifikasi melalui DevSpace host ini.
4. Auto-detect saat **dua adaptor FT232R dipasang bersamaan** menolak memilih
   perangkat secara acak. Perlu receiver multi-device jika ingin akuisisi
   simultan, atau satu perangkat per sesi saat ini.
