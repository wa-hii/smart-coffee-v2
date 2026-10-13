# USB read-only 15 detik — FT232R disconnect pada saat open

**Tanggal/waktu:** 13 Oktober 2026, sekitar 19.24 WIB.
**Perangkat:** Smart Coffee E-Nose PCB custom ATmega2560,
USB FT232R → Raspberry Pi 5.
**Hasil:** **BLOCKED / USB DISCONNECTED**; tidak ada
pembacaan JSON atau perubahan firmware/aktuator.

## Addendum — pemeriksaan ulang setelah operator menyatakan restart (19:41 WIB)

Operator menyampaikan **"sudah di restart, jalankan ulang"**.
Pemeriksaan pasif melalui SSH Pi dilakukan tanpa
membuka `/dev/ttyUSB*`, tanpa reset host/hub, dan
tanpa mengirim byte UART.

- Waktu cek Pi **2026-10-13 19:41:32 +07:00**.
- `lsusb -d 0403:6001`: **kosong**.
- `lsusb -t`: hanya root hub USB pada Bus 001–004,
  **tidak ada FT232R**.
- `/dev/serial/by-id` dan `/dev/ttyUSB*`:
  **tidak ada**.
- Log kernel yang relevan berakhir pada **USB
  disconnect 19:24:44**, tidak menunjukkan
  enumerasi FT232R berikutnya.
- `vcgencmd get_throttled`: `throttled=0x0`.
- `uptime -s` menunjukkan **14:24:00 WIB**,
  jadi Raspberry Pi **tidak terlihat reboot**
  setelah kehilangan FT232R. Bagian mana yang
  di-restart operator belum dikonfirmasi.

**Keputusan:** USB transport tetap **BLOCKED**,
tidak ada pembacaan serial 15s baru atau G3 ulang.
Verifikasi fisik kabel USB dan jalur daya FT232R
masih diperlukan sebelum mencoba serial lagi.

## Addendum — konfirmasi fisik dan enumerasi pasif ulang (19:33 WIB)

Pengguna mengonfirmasi bahwa **PCB custom dan LCD
Nextion masih menyala normal**, serta **kabel USB
masih terpasang pada kedua ujungnya**. Ini
merupakan observasi operator atas alat; **belum
menjamin bahwa jalur D+/D−, VBUS, GND, atau
power internal FT232R bekerja normal**.

SSH ke `enose-pi5` berhasil, lalu diperiksa
`lsusb`, `lsusb -t`, `/dev/serial/by-id`,
`/dev/ttyUSB*`, `/sys/bus/usb/devices/3-1`,
`vcgencmd get_throttled`, dan catatan kernel.
**Tidak ada port serial yang dibuka**.

Hasil:
- Keempat USB root hub Pi tetap terlihat
  pada Bus 001–004.
- `lsusb -d 0403:6001` **kosong**;
  **tidak ada FT232R**, port `ttyUSB0`,
  device by-id maupun node sysfs `3-1`.
- Catatan kernel terakhir untuk FT232R
  tetap **19:24:44 WIB: USB disconnect**;
  tidak ada bukti enumerasi ulang sesudahnya.
- `throttled=0x0`, tidak ada
  proses listener G3 yang masih berjalan.

**Diagnostik terkini:** karena PCB dan Nextion
hidup tetapi bridge USB tidak terenumerasi,
prioritaskan pemeriksaan fisik kabel USB-B/A,
konektor, VBUS/ground dan suplai FT232R
oleh penanggung jawab hardware dengan
prosedur daya aman. Jangan menyimpulkan
firmware/baud/parser sebagai penyebab
untuk kegagalan enumerasi; serial parsing
baru relevan sesudah USB terlihat lagi.

**Tindakan selanjutnya:** hentikan sesi
akuisisi, matikan daya secara tertib
sesuai SOP lokal sebelum pemeriksaan
kabel/konektor; dokumentasikan hasil
inspeksi. Jangan mencabut kabel atau
mengukur PCB saat masih bertegangan
tanpa prosedur/proteksi yang sesuai.
Setelah kondisi fisik dinyatakan aman
dan sambungan dipulihkan operator,
lakukan **enumerasi pasif** dahulu.
Tidak ada izin auto-retry membuka port.

## Scope dan izin

Operator mengizinkan satu pembacaan **USB read-only
15 detik**, tanpa START AI TEST dan tanpa TX perintah
ke ATmega. Pengujian memakai listener
`scripts/stage7_pi_adapter.py` dengan
diagnostik `other_json_key_signatures` (field names
dan frekuensi saja, tanpa payload sensor).

## Fakta preflight

- Pi `enose-pi5` aktif melalui SSH dengan verifikasi
  host key (`HostKeyAlias=enose-pi5`).
- FT232R `A10KMM3S` terenumerasi sebagai
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`
  → `/dev/ttyUSB0`.
- `fuser /dev/ttyUSB0` tidak menampilkan pemilik,
  `serial-getty` dan `ModemManager` inactive,
  `vcgencmd get_throttled=0x0`.
- Hash skrip Pi:
  `5628304575b3d28d2234106b5f198e8670614b82301174206429df2b`.
- `test_stage7_pi_adapter.py` **PASS offline Pi**.
- Nama output baru
  `results/pi_stage7/custom_pcb_usb_schema_idle_15s_run01.json`
  belum ada sebelum percobaan.

## Gejala dan bukti

Satu kali membuka UART via `serial-readonly`,
`115200`, durasi maksimal `15`, berakhir dengan:

```text
serial.serialutil.SerialException: [Errno 19]
could not open port ...A10KMM3S-if00-port0:
[Errno 19] No such device
```

Log kernel Pi menunjukkan pada **19:24:44 WIB**:

```text
ftdi_sio ttyUSB0: ftdi_set_termios FAILED to set databits/stopbits/parity
ftdi_sio ttyUSB0: ftdi_set_termios urb failed to set baudrate
ftdi_sio ttyUSB0: failed to set flow control: -19
usb 3-1: USB disconnect, device number 2
ftdi_sio ttyUSB0: FTDI USB Serial Device converter now disconnected from ttyUSB0
ftdi_sio 3-1:1.0: device disconnected
```

Pemeriksaan pasca-kegagalan (read-only):

| Item | Hasil |
|---|---|
| `lsusb -d 0403:6001` | tidak menemukan FT232R |
| `/dev/serial/by-id`, `/dev/ttyUSB*` | tidak ada FT232R |
| Proses listener | sudah berhenti |
| Pi power | `throttled=0x0` |
| Output JSON 15 detik | **tidak terbentuk** |
| Data JSON/sensor diambil | **tidak ada** |
| TX perintah dari Pi | **tidak ada** |
| Upaya open ulang | **tidak dilakukan** |

**Interpretasi:** perangkat USB terputus secara
fisik/logis pada saat inisialisasi port dan belum
terenumerasi lagi ketika diperiksa. Ini adalah
**korelasi waktu**, bukan bukti sebab.
Penyebab dapat berupa kabel/konektor, suplai daya
PCB/custom FT232R, sambungan USB, atau reset
perangkat; belum ada diagnosis kelistrikan.
Status Pi throttle normal tidak membuktikan rail PCB
eksternal aman atau tidak berfluktuasi.

## Next action / safety stop

Jangan mengulangi serial open otomatis,
mereboot perangkat, mengubah wiring saat hidup,
atau mengaktifkan G3. Operator perlu memastikan
alat kembali aman/IDLE, kabel USB-B/A masih
terpasang dengan baik, adaptor/sakelar PCB menyala,
dan tidak ada perubahan layar/perilaku pompa/valve.
Lakukan pemeriksaan fisik USB/catu setelah aman,
kemudian enumerasi pasif Pi; **minta izin baru**
sebelum percobaan buka serial berikutnya.

Hasil G2 sebelumnya (4.313 byte) dan G3 Run02
(52.224 byte / 189 JSON tidak dikenali) adalah
bukti historis berbeda; tidak dapat digunakan
untuk menyatakan pembacaan 15 detik ini berhasil.
