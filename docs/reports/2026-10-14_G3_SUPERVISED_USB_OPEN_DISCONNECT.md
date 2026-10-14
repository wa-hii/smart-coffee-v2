# G3 supervised — USB open failure, capture tidak dimulai

**Waktu:** 14 Oktober 2026 sekitar 16:23–16:24 WIB.
**Operator:** menyatakan onsite, device IDLE/pengawasan aman,
dan G0 USB/backfeed sudah diperiksa aman oleh pihak onsite.
Pernyataan operator tidak diganti dengan bukti pengukuran
kelistrikan yang independen.

## Preflight read-only (Pi)

- SSH pulih, host `enose-pi5`, Raspberry Pi 5 Model B Rev 1.1.
- `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`
  menunjuk `/dev/ttyUSB0`, FT232R `0403:6001`.
- `fuser` tidak memperlihatkan pengguna port; getty dan
  ModemManager inactive; `vcgencmd get_throttled=0x0`.
- Hash Pi adapter `bfd6ea16d259ab0914daec6afa09d90c9b2a6d9bd00dff45631f2d78bb9028e0`
  dan shared framer `3e091a76429017a3a055b14820b0617ff8462907f0b1588624b497ee162c0d29`
  cocok dengan frozen RC1. Offline test Pi PASS.

## Percobaan listener G3 fisik (satu kali)

Listener `stage7_pi_adapter.py serial-readonly` disiapkan
untuk membaca saja, baud 115200, maksimal 180 detik,
evidence tujuan `results/pi_stage7/g3_supervised_live_20261014_1624.json`.
TIDAK ada start/stop/inference/actuator command dikirim,
dan **operator belum diberi instruksi menekan START**.

Saat `pyserial.open()` Pi mengembalikan:

`serial.serialutil.SerialException: [Errno 19] No such device`.

Log kernel tepat **2026-10-14 16:24:01 WIB**:

```text
ftdi_sio ttyUSB0: ftdi_set_termios FAILED to set databits/stopbits/parity
ftdi_sio ttyUSB0: ftdi_set_termios urb failed to set baudrate
ftdi_sio ttyUSB0: failed to set flow control: -19
usb 3-1: USB disconnect, device number 2
ftdi_sio ttyUSB0: FTDI USB Serial Device converter now disconnected from ttyUSB0
```

Recheck 16:24:44: FT232R tidak ada di `lsusb`, direktori
`/dev/serial/by-id` dan `/dev/ttyUSB0` hilang, Pi masih
`get_throttled=0x0`. **Tidak ada file evidence JSON live
yang dibuat** karena gagal sebelum sesi aktif.

## Keputusan QA dan pemulihan

- **G3 = BLOCKED_USB_DISCONNECT**, bukan PASS, bukan
  NOT_STARTED karena user lupa menekan tombol, dan bukan
  kegagalan inferensi.
- Penyebab fisik/USB spesifik **belum diketahui**; kernel
  hanya membuktikan disconnect bersamaan dengan serial open.
- Tidak dilakukan reboot, reset USB software, firmware flash,
  kalibrasi, atau retry serial otomatis.
- Pengujian aktif selanjutnya menunggu pemulihan enumerasi
  FT232R oleh operator onsite dengan SOP G0 dan kondisi IDLE,
  lalu preflight serta pemeriksaan stabilitas G2. Listener
  G3 hanya dijalankan lagi jika port sehat dan supervisi ada.
- Frozen software RC1 tag `pre-onsite-software-2026-10-14-rc1`
  tidak diubah; laporan ini merupakan bukti QA hardware tambahan.

## Addendum 16:28–16:29 WIB: replug USB belum memulihkan controller

Operator onsite mengonfirmasi kabel USB telah dilepas dan
dipasang ulang sekali sesuai instruksi. Pemeriksaan SSH
read-only setelah tindakan:

- Pi 5 masih hidup, uptime tidak reset (`2026-10-13 19:49:19`),
  SSH tetap tersedia, `vcgencmd get_throttled=0x0`.
- `lsusb` hanya menampilkan empat root hub Linux; **tidak ada
  FT232R 0403:6001**. `/dev/ttyUSB0`, `/dev/serial/by-id`
  serta node USB `3-1` tidak ditemukan.
- Kernel mencatat tepat pukul **16:24:01 WIB** sebelum
  `ftdi_set_termios` gagal:

```text
xhci-hcd xhci-hcd.1: xHCI host not responding to stop endpoint command
xhci-hcd xhci-hcd.1: xHCI host controller not responding, assume dead
xhci-hcd xhci-hcd.1: HC died; cleaning up
```

- Tidak ada log attach/enumerasi FT232R baru setelah operator
  melakukan replug USB. Ini menguatkan bahwa kegagalan
  **USB host controller** menghalangi enumerasi, tetapi
  **tidak membuktikan** akar sebab fisik/kabel/FT232R/PSU/driver.
- Keputusan: **JANGAN retry membuka serial atau tekan START**.
  Pemulihan berikutnya bisa berupa reboot **hanya Raspberry Pi**
  dalam kondisi PCB idle dan pengawasan onsite, tetapi
  tindakan reboot menunggu izin spesifik dari operator.
  Sesudah pemulihan: observasi enumerasi dan kernel,
  verifikasi `fuser`, `throttled`, dan satu G2 read-only
  terawasi sebelum satu G3.
