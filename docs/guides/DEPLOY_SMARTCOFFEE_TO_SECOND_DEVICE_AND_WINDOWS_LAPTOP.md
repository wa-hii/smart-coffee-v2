# Deploy Smart Coffee E-Nose v2 ke alat kedua dan laptop Windows lain

Panduan ini berlaku untuk **PCB kompatibel ATmega2560 + ADS1115 x4 + TFT Nextion seri NX4827T043_011** dan firmware di branch `wahyu`, build ID `take12-abs900-no-uiwait-20261017`. Untuk hardware/model layar yang berbeda, **jangan flash tanpa cek pinout, voltase, alamat I²C, dan kompatibilitas bootloader**.

## 0. Pastikan unit pertama aman

Jangan cabut USB, menghentikan receiver, membuka Serial Monitor/COM yang sama, atau flashing board saat unit pertama sedang Take Data. Semua langkah untuk alat kedua di bawah dijalankan pada **laptop dan perangkat yang berbeda**. CSV historis tidak otomatis ditransfer dari unit pertama.

## 1. Firmware ATmega2560 untuk alat kedua

Pada laptop yang digunakan untuk **build dan upload**, pasang VS Code + PlatformIO atau PlatformIO Core CLI, driver FTDI (`0403:6001`) dan Git. Clone repo terbaru:

```powershell
git clone -b wahyu --single-branch https://github.com/wa-hii/smart-coffee-v2.git SmartCoffeeV2
cd SmartCoffeeV2
pio run -e mega2560
pio device list
```

Setelah colok **USB FTDI dari alat kedua**, lihat COM aktual pada `pio device list`/Device Manager. Misalnya COM7:

```powershell
pio run -e mega2560 -t upload --upload-port COM7
```

Ganti `COM7` sesuai hasil deteksi; jangan mengasumsikan `COM4` dari unit pertama. Tunggu AVRDUDE melaporkan signature ATmega2560 **`0x1e9801`**, flash verification sukses, dan PlatformIO **SUCCESS**. Firmware build ID `take12-abs900-no-uiwait-20261017` mengatur Take Data 30 siklus (25 s purge + 5 s collect), AI Test 5 siklus, Nextion 12 halaman melalui **Serial2 @ 9600**, dan baseline ADC 60 sampel. Proses build tidak mencampur CSV ataupun menulis EEPROM. Hindari menghidupkan flag R0-calibration tanpa SOP dan otorisasi.

**Penting:** Satu port COM hanya boleh dipegang satu aplikasi. Tutup receiver *alat kedua* saat idle sebelum upload; setelah selesai, tutup Serial Monitor bila dibuka sebelum menjalankan receiver. Jangan menghentikan receiver alat pertama yang sedang merekam.

## 2. TFT/HMI untuk LCD Nextion alat kedua

Gunakan sumber HMI versi 12 halaman yang telah diverifikasi:

`nextion/NX4827T043_011/project/RoastSense_12P_EDITOR_REPAIRED_SAFE_20261017.HMI`

Buka di Nextion Editor, pastikan model LCD sesuai, kemudian **Compile dan Debug hingga 0 Errors**. Ekspor/Save As `.tft` dan upload ke LCD Nextion **alat kedua**, bukan unit pertama. Jangan memakai `build/*.tft` lama tanpa memeriksa tanggal/sumber: file tersebut mungkin bukan hasil compile terkini. Cek `pDataRun` ID 3, `pDataDone` ID 4, dan navigasi awal di LCD.

Firmware/TFT **tidak otomatis tersalin** ke layar hanya karena firmware ATmega di-upload; proses flashing keduanya terpisah.

## 3. Laptop kedua hanya untuk mengambil CSV (tanpa PlatformIO)

Unduh file versi terbaru dari branch `wahyu`:

`dist/Smart_Coffee_ENose_USB_Receiver_Windows_v3_Timing900.zip`

1. Di laptop kedua Windows 10/11, instal **Python 3.10+ 64-bit** dan driver FT232R. Instalasi awal library Python perlu koneksi internet.
2. Ekstrak ZIP **sampai lengkap**, misalnya ke `Documents\SmartCoffee_Receiver`. Hindari ekstraksi di folder `Program Files`, jangan menjalankan langsung dari jendela ZIP.
3. Klik dua kali `windows_receiver\INSTALL_ON_THIS_LAPTOP.bat`. Script membuat virtualenv, memasang `pyserial`, `numpy`, `pandas`, menjalankan diagnostik, memasang shortcut startup, dan memulai listener pasif.
4. Hubungkan USB FTDI alat kedua ke laptop kedua. Nomor port boleh COM3/4/7/dst; **auto-discovery** memilih FTDI yang cocok, dengan perlindungan bila ada beberapa adaptor kompatibel.
5. Periksa `logs\acquisition_service.status.json`. Harus `state: connected` ke COM yang benar **sebelum START pada LCD**.
6. Pilih roast, origin dan batch pada LCD lalu jalankan **Take Data**. Receiver menunggu `ACQ_START`, menyimpan baris sensor 1 Hz ke file staging, lalu hanya mengesahkan CSV setelah `ACQ_COMPLETE` dan QA lolos. Hasil ada di `data\raw\NAMA_BNN.csv`; baseline terpisah di `data\baseline`; sesi gagal/disconnect masuk `data\raw\incomplete`.

**Tidak perlu Python di ATmega atau Nextion.** CSV dibuat oleh receiver yang berjalan di Windows; tidak otomatis dibuat pada mikrokontroler. Auto-start berarti berjalan sesudah login Windows, bukan perangkat USB langsung menjalankan program.

## 4. QA, komponen baru, dan keamanan data

- Di laptop yang berbeda, **satu alat → satu receiver → satu port COM**. Jangan mencoba mengambil stream USB yang sama di dua laptop bersamaan tanpa desain jaringan/relay tambahan.
- Untuk firmware timing baru, receiver v3 memeriksa `elapsed_active_ms` dengan target **900.000 ms waktu aktif** (Pause tidak dihitung). Durasi yang meleset >=1 detik atau data parsial ditahan sebagai `incomplete`. Tidak dibuat baris sensor sintetis.
- Jika COM tidak terdeteksi, jalankan `windows_receiver\TEST_PORT_DETECTION.bat`, `DIAGNOSE_WINDOWS_10.bat`, lalu baca `logs\acquisition_service.log`. Jangan membuka monitor serial saat receiver sudah terhubung.
- **Setiap alat punya karakteristik sensor dan kalibrasi berbeda**. Jangan menyalin EEPROM R0 dari alat lain. Baseline baru harus diambil sendiri sesuai SOP clean-air. Jika kualitas ADC/baseline gagal, hentikan pengukuran dan investigasi hardware terlebih dahulu.
- Untuk memindahkan data **lama**, salin file CSV lengkap yang sudah disahkan dari `data/raw`, bukan staging/incomplete; jangan timpa file dengan nama sama tanpa audit metadata.
- Package receiver versi v3 dibuat dari code branch `wahyu` terbaru, bukan ZIP v2 yang belum memasukkan QA durasi.
