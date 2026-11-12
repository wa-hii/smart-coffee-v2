# PCB kedua — upaya deployment RF30 via SSH, bootloader belum merespons

**Tanggal:** 12 November 2026 sekitar 17:15–17:18 WIB. **Branch:** `wahyu`.

## Tujuan dan otorisasi

Operator mengatakan pemeriksaan fisik dan empat prasyarat telah dilakukan, lalu memberi izin eksplisit untuk melanjutkan upload sampai tahap akhir. Target adalah **PCB ATmega2560 kedua**, bukan ATmega COM5/SVM30 historis. Raspberry Pi 5 diakses melalui `enose-v3@enose-pi5` (SSH/Tailscale), FT232R serial `A10KNJBL`.

## Pemeriksaan sebelum upload

- SSH berhasil; uptime Pi sekitar 1 jam 30 menit; `vcgencmd get_throttled=0x0`.
- Port by-id `usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0` masih menuju `/dev/ttyUSB0`; `fuser` tidak menemukan pemilik.
- Kernel hanya mencatat disconnect/reconnect FT232R pukul 17:01 WIB dari sebelum percobaan saat ini.
- SHA256 firmware kandidat RF30 di Pi:
  `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
- SHA256 model RF500 di Pi:
  `b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`.
- Tool `avrdude` 7.1 disiapkan sebelumnya di Pi secara terisolasi. Tidak dibutuhkan COM5 Windows.

## Hasil pengecekan bootloader yang diulang

Sebelum perintah flash, dilakukan **satu percobaan membaca signature** lewat `avrdude` pada adaptor yang sama. Pilihan `-c wiring -b 115200` didasarkan pada firmware/board historis dan **belum dapat dikonfirmasi untuk PCB kedua**.

```text
avrdude -p m2560 -c wiring
  -P /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0
  -b 115200 -n -v
```

Pembatas waktu eksternal: **15 detik**. Hasil:

```text
avrdude stk500v2_recv() error: timeout
avrdude stk500v2_recv() error: timeout
Process exited with code 124 (timeout)
```

**Chip signature tidak dibaca, tidak ada pengakuan dari bootloader, dan tidak ada perintah menulis Flash/EEPROM.** Prosedur upload sengaja tidak dipanggil karena programmer belum berhasil terhubung ke target. Opsi `-n` menandakan operasi no-write pada percobaan tersebut, bukan bukti kondisi firmware chip.

## Pemeriksaan setelah percobaan

- SSH masih aktif, `throttled=0x0`, `/dev/ttyUSB0` masih muncul.
- Journal tidak memiliki disconnect baru setelah 17:01; tidak ditemukan `xHCI dead` baru.
- `lsusb` hanya memperlihatkan root hub dan FT232R `0403:6001`; **tidak ada programmer ISP USB terdeteksi**.
- Pencarian file `*.hex` dan nama yang mengandung `eeprom` di bawah `/home/enose-v3` dengan kedalaman hingga 8 folder hanya menemukan kandidat firmware RF30, **bukan backup asli alat baru**. Ini tidak membuktikan operator belum melakukan backup di lokasi lain; bukti rollback belum tersedia dalam lokasi yang diakses sesi ini.
- Readiness RF Pi masih `HOST_STAGED_NOT_MCU_VERIFIED` dengan `live_activation_allowed=false`.

## Keputusan teknis

**RF30 belum terpasang. NO-GO untuk mengunggah firmware atau menyalakan bridge live pada PCB kedua sampai programmer bisa membaca signature, backup Flash/EEPROM PCB kedua dapat diverifikasi, dan rollback tersedia.** Permintaan untuk mengabaikan langkah pemeriksaan tidak dapat menggantikan respons perangkat fisik yang tidak ada.

Diagnostik yang relevan untuk onsite: verifikasi koneksi **TX/RX silang, ground bersama, level UART, DTR/RESET dan bootloader ATmega2560**; bila bootloader tidak tersedia, siapkan programmer ISP yang benar melalui ICSP untuk *readback* sebelum flashing. Jangan memakai image backup SVM30 yang berasal dari PCB lain. Jangan mencoba baud/RESET/flash berulang tanpa membuktikan wiring.

**Tahap yang berhasil:** paket RF30 dan RF500 siap dan diverifikasi di Pi, tool programmer dapat berjalan, akses USB/SSH terdeteksi. **Tahap yang belum berhasil:** identifikasi signature, backup/rollback PCB baru, upload aplikasi, boot `pHome`, streaming 30 siklus/900 sampel dan ACK klasifikasi fisik.
