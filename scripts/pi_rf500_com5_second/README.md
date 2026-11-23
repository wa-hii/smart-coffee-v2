# Raspberry Pi 5 kedua — integrasi RF500 untuk board utama COM5

## Status 23 November 2026 — deployment berhasil; listener idle READY

- Pi kedua `raspi5@raspberrypi` (`100.94.161.96`) telah menerima
  source RF500, `pi_labeled_take_data.py`, model asli dan metadata.
- USB terverifikasi `0403:6001`/`A10KMM3S` → `ttyUSB0`;
  Pi power `throttled=0x0`; validasi model dan bridge PASS.
- PyPI gagal diakses, dependensi pada Debian 13/Python 3.13.5
  dicopy dari lingkungan Pi pertama dalam tar terverifikasi;
  *import* lima library utama PASS.
- `installer.py --check` PASS, `--install` terverifikasi di cron,
  `--start` menghasilkan `COM5_PI2_PERSISTENT_LISTENER_READY`.
  Supervisor PID awal 2114, child listener 2123;
  log `RF500_PERSISTENT_READY`, *capture* idle.
- **Belum teruji:** AI Test 900 frame, Take Data CSV baru,
  RF500→ATmega ACK fisik, dan boot ulang Pi. HMI menu dilaporkan
  aman oleh operator; sesi ini tidak menekan tombol apa pun.

Catatan di bawah tentang keadaan *belum dipasang* adalah
**riwayat per 18–20 November**, bukan status sekarang.

Target **khusus**: Tailscale `100.94.161.96`, hostname terdeteksi
`raspberrypi`, board utama ATmega2560 ber-firmware
`take30-ai30-rfhost-20261110`, dan adaptor USB FT232RL
Windows COM5 `A10KMM3SA` (Linux diperkirakan `A10KMM3S`).
Jangan salin pengaturan FTDI Raspberry Pi pertama
`A10KMZQJ` ke Pi ini.

## Update 20 November 2026 — akses akun dan modul penyimpanan CSV

Username Pi kedua telah diketahui: `raspi5`. Tailscale IP
target tetap `100.94.161.96`, tetapi akses SSH dari
komputer konektor Windows **masih belum diotorisasi**.
User dapat login melalui terminalnya sendiri.
Komputer konektor sudah menyiapkan kunci SSH khusus
`~/.ssh/id_ed25519_enose_pi2`, yang **hanya kunci
publiknya** perlu ditambahkan pengguna ke
`~/.ssh/authorized_keys` di Pi kedua. Jangan
menyalin kunci privat atau password ke GitHub/chat.

Model RF500 asli dan metadata berhasil diambil dari
Pi pertama ke folder privat Windows
`%LOCALAPPDATA%\SmartCoffee\pi2_rf500_20261120`,
hash model diverifikasi
`b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
Model tetap tidak di-push ke repository.

Paket deploy **terbaru** sekarang menyalin
`pi_labeled_take_data.py` dan
`roast_rf30_pi_stream_replay.py` selain file
RF500 lama. Ini wajib supaya listener dapat
menjalankan **Take Data (CSV 900 baris)** dan
**AI Test** tanpa error `ModuleNotFoundError`.
Installer memeriksa semua dependensi tersebut
sebelum membuka serial.

Setelah kunci publik diotorisasi, dari PowerShell
Windows di root repo:

```powershell
./scripts/pi_rf500_com5_second/deploy_from_windows.ps1 `
  -SshUser raspi5 `
  -ModelPath "$env:LOCALAPPDATA\SmartCoffee\pi2_rf500_20261120\final_model.joblib" `
  -MetadataPath "$env:LOCALAPPDATA\SmartCoffee\pi2_rf500_20261120\final_model_info.json" `
  -EnableAutostart
```

**Belum ada program terpasang pada Pi kedua** ketika
bagian ini diperbarui. Jangan memulai AI Test
sampai `COM5_PI2_PERSISTENT_LISTENER_READY`
terkonfirmasi pada perangkat kedua.

## Kondisi autentikasi 18 November 2026

Alamat Tailscale dapat diping dari laptop Windows,
tetapi SSH ke `100.94.161.96` dengan akun
`enose-v3`, `pi`, ataupun `wahyu` menghasilkan
`Permission denied (publickey,password)`.
**Belum ada file ditransfer, perintah dijalankan, atau listener diaktifkan
pada Pi kedua.** Kredensial SSH tidak boleh dimasukkan
ke kode maupun GitHub. Masuk ke Pi dengan akun lokal sah
melalui terminal/konsol; aktifkan SSH autentikasi milik
operator jika perlu, atau gunakan PowerShell interaktif
agar password diminta langsung pada laptop.

## Prasyarat

1. SSH ke Pi `100.94.161.96` berhasil dengan **username yang benar**.
2. USB board utama COM5 sudah terpasang; di Pi harus ada
   `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`.
   Ini kandidat Linux dari nomor seri Windows; **harus
   diverifikasi melalui `udevadm`**. Jika tidak cocok,
   hentikan deployment dan lihat identitas perangkat yang sebenarnya.
3. Model RF500 **persis** dari Pi pertama:
   `final_model.joblib` SHA256
   `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`,
   beserta `final_model_info.json`. Jangan gunakan
   model baru atau `joblib` tanpa checksum yang benar.
4. Python 3 dengan modul `venv`, akses `pip` dan Internet
   untuk install scikit-learn 1.7.2, joblib 1.6.0,
   pyserial 3.5 dan dependensi kompatibel.

Model asli tidak berada di checkout Windows pada saat
persiapan ini; model harus ditransfer dari
`~/smart-coffee-stage7/rf30_staging/` pada Pi pertama
oleh operator yang memiliki akses sah. File binary
tidak pernah dimasukkan ke repo GitHub.

## Setelah SSH dapat digunakan

Dari PowerShell Windows, setelah mengambil model asli
dan metadata ke folder pribadi Windows:

```powershell
./scripts/pi_rf500_com5_second/deploy_from_windows.ps1 `
  -SshUser USER_PI_KEDUA `
  -ModelPath 'C:\lokasi\final_model.joblib' `
  -MetadataPath 'C:\lokasi\final_model_info.json' `
  -EnableAutostart
```

Skrip ini mengunggah kode ke
`~/smart-coffee-stage7/rf30_staging/com5_integration/always_on/`,
menyiapkan `.venv`, memeriksa serial FT232RL, IP
Tailscale, hash model, API bridge, keadaan catu daya
dan izin UART, kemudian memasang user `cron @reboot`
dan menjalankan listener. Tidak menulis Flash, EEPROM,
Nextion atau mengaktifkan AI Test secara otomatis.

Untuk transfer kode **tanpa model** (tidak ada listener aktif):

```powershell
./scripts/pi_rf500_com5_second/deploy_from_windows.ps1 `
  -SshUser USER_PI_KEDUA -StageCodeOnly
```

## Perintah pemeriksaan di Raspberry Pi kedua

Setelah login sebagai user yang menginstal program:

```bash
tailscale ip -4
ls -l /dev/serial/by-id/
udevadm info --query=property --name=/dev/ttyUSB0 | grep -E 'ID_(VENDOR_ID|MODEL_ID|SERIAL_SHORT)'
~/smart-coffee-stage7/rf30_staging/.venv/bin/python -B \
  ~/smart-coffee-stage7/rf30_staging/com5_integration/always_on/installer.py --check
tail -f ~/smart-coffee-stage7/rf30_staging/com5_integration/always_on/supervisor.log
```

Hasil yang diharapkan setelah `--start`:
`RF500_PERSISTENT_READY`; lantas Pi akan siap
menunggu `ACQ_START` dari tombol Nextion.
Uji 30 siklus/900 sampel dan
`RF500_MCU_ACK_CONFIRMED` tetap **harus dilakukan
secara fisik** sebelum klaim end-to-end PASS.

Jangan menjalankan listener baru bersamaan dengan
serial monitor atau program lain yang membuka FTDI itu.
R0 yang belum dikalibrasi serta validasi lintas alat
masih menjadi keterbatasan akurasi AI.
