# Pengambilan data 3 E-Nose pada 1 laptop — COM5 / COM6 / COM7

**Update v7 frame diagnostics:** apabila sesi berpindah ke `incomplete`
karena `serial frame corrupt or oversized`, receiver baru mencatat alasan
terpisah `SERIAL FRAME REJECTED reason=malformed_json` (dengan `detail` dan
`frame_bytes`) atau `reason=oversized_line` (`limit_bytes=4096`). Tidak
mencatat isi mentah frame dan **tetap tidak meloloskan dataset rusak**.
Paket terbaru: `Smart_Coffee_ENose_USB_Receiver_Windows_v7_SerialFrameDiagnostics.zip`.
File v5 yang lama **tidak menyimpan rincian penyebab ini**; menginstal v7
tidak dapat mengungkap paket serial yang sudah lewat.

Jika beberapa alat melaporkan masalah di siklus berbeda, prioritas inspeksi
ketika semuanya IDLE adalah kestabilan USB data/driver FTDI, kabel, catu
daya USB hub, dan apakah Nextion/MCU sedang reboot atau mengeluarkan JSON
tidak valid. Jangan meningkatkan `MAX_LINE_BYTES` atau mengabaikan
`TRANSPORT_ERROR` sebagai jalan pintas: satu pesan normal jauh lebih pendek
daripada 4096 byte dan data tidak valid tidak boleh menjadi label training.

**Update v6 diagnostik (19 Oktober 2026):** gunakan ZIP
`Smart_Coffee_ENose_USB_Receiver_Windows_v6_ThreeDevices_Diagnostics.zip`.
Paket ini mempertahankan protokol dan lokasi CSV v5 serta menambahkan
`windows_receiver/DIAGNOSE_THREE_SESSIONS.bat`. Laporan hanya membaca
status/log/final/incomplete/partial dan daftar COM. Bisa dipakai saat
Take Data berlangsung tanpa membuka COM. Supervisor tetap mendukung
COM5/6/7 dan USB serial identity seperti v5.

**Jika COM tiba-tiba hilang dan muncul `ClearCommError failed (Access is
denied)`/`usb_not_found`:** catat identitas alat, USB serial, waktu, log,
dan lokasi incomplete. Ini merupakan kegagalan transport yang tidak boleh
diubah menjadi file CSV lengkap atau dipulihkan dengan mengarang sampel.
Tinjau kabel USB data, hub/port USB berdaya cukup, FTDI driver, Device
Manager, dan Windows USB power management **setelah alat IDLE**. Koneksi
yang tersambung kembali hanya dapat menerima sesi *baru*; tidak otomatis
memulihkan sesi 30 siklus yang telah kehilangan 303 sampel.

**Kegagalan pengambilan kedua:** CSV final hanya diterbitkan ketika
`ACQ_COMPLETE` dan validasi PASS. Pada sesi aktif CSV masih berada di
`data/raw/devices/ALAT_N/.incoming/`. Jika tidak muncul hasil kedua,
periksa log alat tersebut: ada/tidak `ACQ START`, `ACQ COMPLETE`, `Timing
QA PASS`, `ACQ INCOMPLETE`, dan `Acquisition validation PASS`. Jangan
menutup terminal receiver sebelum seluruh sesi selesai.

**Didukung oleh receiver multi-device v5.** Setiap ATmega2560 mengirim data
melalui FT232R/USB ke port Windows sendiri. Tombol **Take Data** pada masing-
masing LCD Nextion menjalankan 30 siklus secara independen. Receiver PC bersifat
pasif dan **tidak mengirim perintah START, tidak flash, tidak mengaktifkan valve**.

## Instalasi di laptop lama (Windows 10/11)

1. Ekstrak `Smart_Coffee_ENose_USB_Receiver_Windows_v7_SerialFrameDiagnostics.zip`
   ke folder baru di `Documents` (jangan jalankan di dalam ZIP). Jangan menimpa
   folder receiver v3/v4 atau data raw sebelumnya.
2. Setelah semua alat **IDLE**, tutup receiver lama, lalu **nonaktifkan shortcut
   Startup lama** melalui folder `shell:startup` (cadangkan shortcut lama;
   jangan hapus file CSV). Jika receiver lama masih aktif, jangan lanjut.
3. Jalankan `windows_receiver/INSTALL_THREE_ON_THIS_LAPTOP.bat` sekali.
   Ini memasang Python dependencies dan preflight *tanpa* membuka COM,
   *tanpa* memasang auto-start single-device.
4. Hubungkan ketiga alat secara terpisah melalui USB, cek Device Manager
   bahwa alat fisik 1 = COM5, alat 2 = COM6, alat 3 = COM7. Cek USB serial
   number untuk mencegah salah label alat. Bila memakai hub, gunakan hub
   berkualitas dengan catu daya yang memadai.
5. Jalankan `windows_receiver/START_THREE_ENOSE_COM5_COM6_COM7.bat`.
   Pertama script menampilkan mapping read-only. Jika benar dan alat IDLE,
   ketik `START`. Alternatif via PowerShell dari folder `SmartCoffee_Receiver`:

   ```powershell
   .\.venv\Scripts\python.exe scripts\multi_device_receiver.py --ports COM5 COM6 COM7
   .\.venv\Scripts\python.exe -u scripts\multi_device_receiver.py --ports COM5 COM6 COM7 --start
   ```

   **Perintah pertama hanya audit USB; kedua membuka ketiga COM.**
6. Sebelum menekan Take Data pada layar mana pun, semua status harus
   `connected` pada tiga file ini:

   - `logs/devices/ALAT_1/acquisition_service.status.json`
   - `logs/devices/ALAT_2/acquisition_service.status.json`
   - `logs/devices/ALAT_3/acquisition_service.status.json`

7. Mulai Take Data pada ketiga LCD kapan pun setelah receiver tersambung.
   Pengambilan boleh overlap. Setiap instrumen menghasilkan CSV sendiri;
   **jangan tutup terminal, unplug USB, reboot laptop, membuka Serial Monitor,
   atau mengunggah firmware saat data masih direkam**.

## Lokasi hasil CSV

| Identitas fisik | COM awal | Hasil valid | Hasil terputus | Log |
|---|---|---|---|---|
| ALAT_1 | COM5 | `data/raw/devices/ALAT_1` | `.../ALAT_1/incomplete` | `logs/devices/ALAT_1` |
| ALAT_2 | COM6 | `data/raw/devices/ALAT_2` | `.../ALAT_2/incomplete` | `logs/devices/ALAT_2` |
| ALAT_3 | COM7 | `data/raw/devices/ALAT_3` | `.../ALAT_3/incomplete` | `logs/devices/ALAT_3` |

Nama CSV asli dari Nextion, misalnya `D-GAW_B51.csv`, dipertahankan di folder
masing-masing alat. Tidak ada overwrite jika nama file identik. Validasi
30 siklus dan `ACQ_COMPLETE` wajib PASS sebelum `.csv` final diterbitkan;
data terputus masuk folder `incomplete`.

Kalibrasi (jika dijalankan sesuai SOP) disimpan terpisah di
`data/baseline/devices/ALAT_1`, dan seterusnya.

**Penting untuk machine learning:** ketika dataset digabungkan secara
manual, cantumkan `device_id`/identitas spesimen dan batch sebagai provenance.
Jangan langsung mencampur batch berbeda atau menghapus jejak asal instrumen.
File di folder bersarang tidak otomatis masuk ke plot lama yang hanya mencari
`data/raw/*.csv`.

## COM berubah setelah reconnect

Setiap port preflight juga memeriksa vendor/product ID USB. Jika adaptor FTDI
memiliki serial number yang unik, receiver mengikat ALAT_1/2/3 ke *USB serial*
tersebut: setelah Windows mengubah COM5 menjadi COM8, alat yang sama tetap
di folder ALAT_1. Jika USB serial number tidak tersedia, receiver mengikat
ke COM awal secara statis: **hentikan saat IDLE dan verifikasi ulang port
sebelum mulai sesi baru**. Serial adaptor USB belum tentu adalah ID PCB yang
unik jika adaptor ditukar antarmesin; pertahankan mapping kabel fisik.

## Troubleshooting cepat

- `PREFLIGHT FAIL` → periksa tiga port hadir, drivernya didukung, tidak ada
  dua alat yang punya serial USB identik, dan tidak ada receiver lama aktif.
- `waiting_for_port` atau `Access is denied` → COM sedang digunakan oleh
  receiver/Serial Monitor/PlatformIO lain. Tutup *ketika IDLE*, bukan saat sesi.
- `connected` tetapi CSV kosong → tekan Take Data **setelah** semua connected;
  cek `ACQ START` dan `ACQ COMPLETE` di log perangkat masing-masing.
- File ada di `.incoming` atau `incomplete` → jangan diubah menjadi CSV final;
  baca log untuk timing/validasi/USB timeout.
- `Ctrl+C` hanya ketika semua alat IDLE. Tidak ada cara memperoleh kembali
  sampel yang tidak diterima ketika serial gagal di tengah sesi.

## Status verifikasi

Receiver sudah diuji **offline** dengan tiga proses paralel dan tiga dataset
sintetis 900 sampel yang mempunyai nama sampel/batch sama. Belum diuji pada
tiga perangkat fisik terhubung bersamaan. Sesi pertama perlu diamati secara
langsung sampai ketiga CSV selesai dan lulus validator.
