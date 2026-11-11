# G2 — Kegagalan open serial FT232R / xHCI Raspberry Pi 5

**Tanggal:** 11 November 2026, WIB. **Status: G2 FAILED / HARDWARE NO-GO.**

## Permintaan dan batas pengujian

Operator menyatakan PCB ATmega + Nextion terhubung langsung ke
Raspberry Pi 5 melalui USB, alat dalam keadaan **IDLE**, operator selalu
di dekat perangkat, dan secara eksplisit menyetujui pembacaan G2.
Laptop Windows hanya digunakan untuk remote SSH Tailscale.

Probe `scripts/stage7_usb_readonly_probe.py` membaca USB serial secara
pasif selama **maksimum 12 detik** pada 115200 baud. Tidak dirancang
untuk menulis serial, memulai akuisisi/AI Test, menggerakkan pompa/valve,
atau melakukan flashing. Pembukaan serial oleh pySerial tetap dapat
menimbulkan DTR/reset MCU meskipun DTR/RTS disetel false.

## Persiapan sebelum percobaan

- Identitas FT232R saat ini: `A10KNJBL`, by-id
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0`
  → `/dev/ttyUSB0`; nomor seri berbeda dari PCB historis
  `A10KMM3S`.
- `fuser /dev/ttyUSB0`: tidak ada proses pemilik.
- ModemManager dan serial-getty pada `ttyUSB0`: inactive.
- `vcgencmd get_throttled=0x0` (tidak membuktikan VBUS/backfeed aman).
- Kernel sebelumnya sudah mencatat disconnect/reconnect pukul
  02:29/02:31 serta `usb3-port1 disabled by hub (EMI?)`
  pukul 10:35. Pesan `EMI?` **bukan diagnosis pasti**.
- Probe diperbarui hanya dengan *allowlist* by-id FT232R baru
  `A10KNJBL` (id historis tetap), dan uji regresi mock
  `scripts/test_stage7_usb_readonly_probe.py` **PASS**. Tidak ada
  penerimaan path arbitrary `/dev/ttyUSB0`, dan semua tiga gate
  `--acknowledgment`, `--idle`, `--supervised` masih diwajibkan.
- Salinan isolated probe + `acquisition_schema.py` diletakkan pada
  `/home/enose-v3/smart-coffee-stage7/g2_20261111/` di Pi.

## Satu kali percobaan G2

- Host: `enose-v3@enose-pi5` via SSH, host-key check aktif.
- Saat sebelum open, by-id path cocok ke `/dev/ttyUSB0`;
  port tidak sedang dipakai oleh proses lain.
- G2 dijalankan dengan durasi 12 detik, DTR/RTS false dan
  `exclusive=True`; **hanya satu kali percobaan**.
- **Gagal sebelum masuk loop pembacaan**, pada
  `serial.Serial.open()` / `os.open()`, dengan
  `OSError: [Errno 19] No such device`.
- Tidak ada data UART/firmware `FW_HELLO` diterima. Tidak ada
  `write()` serial, START, flashing, atau pengoperasian aktuator
  oleh perangkat lunak pengujian.
- Karena gagal sebelum `capture()` mengembalikan hasil,
  file evidence JSON probe **tidak dibuat**. Bukti adalah
  traceback SSH dan journal kernel sesudah percobaan.

## Bukti kernel pada 11:59:29 WIB

```text
xhci-hcd xhci-hcd.1: xHCI host not responding to stop endpoint command
xhci-hcd xhci-hcd.1: xHCI host controller not responding, assume dead
xhci-hcd xhci-hcd.1: HC died; cleaning up
usb 3-1: USB disconnect, device number 4
ftdi_sio ttyUSB0: ftdi_set_termios FAILED to set databits/stopbits/parity
ftdi_sio ttyUSB0: ftdi_set_termios urb failed to set baudrate
ftdi_sio ttyUSB0: failed to set flow control: -19
ftdi_sio ttyUSB0: FTDI USB Serial Device converter now disconnected
```

**11:59:57 dan 12:00:48 WIB:** SSH Raspberry Pi masih dapat
diakses, `throttled=0x0`, tetapi `/dev/ttyUSB0` dan
`/dev/serial/by-id/` **tidak lagi ada**. `lsusb` hanya
menampilkan root hubs dan tidak menampilkan FT232R. Tidak ada
percobaan open ulang, USB reset, service restart, reboot, atau flash.

**Interpretasi:** kondisi cocok dengan kegagalan USB xHCI yang
terjadi bersamaan dengan upaya pembukaan serial. Bukti ini
**tidak cukup** untuk menentukan apakah penyebab utamanya
adalah FT232R, kabel, catu daya/VBUS/backfeed, noise/EMI,
port/hub, firmware/controller atau interaksi pada saat open.
MCU mungkin mengalami DTR reset; perilaku fisik Nextion/pompa
perlu dikonfirmasi oleh operator (tidak diukur jarak jauh).

## Gate tindak lanjut

1. **STOP G2/G3** dan jangan ulang serial open/reboot/USB
   unbind/reset lewat remote untuk sementara.
2. Operator di lokasi memeriksa apakah LED PCB/Nextion tetap
   menyala normal, apakah ada restart, pompa/valve bergerak,
   panas abnormal, kabel longgar, atau masalah PSU.
3. Hardprog meninjau skematik FT232R, jalur daya eksternal
   MCU, USB VBUS, pemisahan supply, proteksi reverse current,
   ground dan kemungkinan gangguan beban/pompa. Dua adaptor
   terpisah **bukan** bukti proteksi VBUS.
4. Setelah perangkat benar-benar aman, lakukan pemulihan
   USB/controller secara terawasi menurut SOP, baru cek by-id,
   tidak dengan percobaan open serial berulang.
5. G2 berikutnya memerlukan izin baru; verifikasi versi
   firmware 30 siklus tetap outstanding.
6. Model SVM final 30 fitur dan kompatibilitas preprocessing
   dikerjakan offline secara terpisah; **bukan penyebab yang
   terbukti** untuk error USB ini.
