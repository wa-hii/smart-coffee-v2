# Raspberry Pi 5 kedua — integrasi RF500 untuk board utama COM5

Target **khusus**: Tailscale `100.94.161.96`, hostname terdeteksi
`raspberrypi`, board utama ATmega2560 ber-firmware
`take30-ai30-rfhost-20261110`, dan adaptor USB FT232RL
Windows COM5 `A10KMM3SA` (Linux diperkirakan `A10KMM3S`).
Jangan salin pengaturan FTDI Raspberry Pi pertama
`A10KMZQJ` ke Pi ini.

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
