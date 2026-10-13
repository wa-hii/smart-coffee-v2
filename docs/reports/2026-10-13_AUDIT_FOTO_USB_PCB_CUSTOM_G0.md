# Audit G0 foto USB PCB custom ATmega2560 ↔ Raspberry Pi 5

**Tanggal:** 13 Oktober 2026
**Jenis pemeriksaan:** inspeksi foto operator, riset sumber primer,
inventaris USB Raspberry Pi **read-only**, serta audit SOP.
**Keputusan akhir:** **G0 PARTIAL / BELUM PASS**.
**G2 (buka serial) dan G3 (akuisisi dengan aktuator): NOT RUN**.

## 1. Foto dan topologi yang benar-benar didukung bukti

Foto operator 1 menunjukkan **Raspberry Pi 5**, pendingin kipas,
input catu USB-C dan salah satu port USB-A berisi konektor USB.
Foto operator 2 menunjukkan sisi depan **perangkat PCB custom**,
dengan port USB yang tampak berbentuk **USB Type-B**, konektor
DB9 9-pin, input adaptor DC barrel serta sakelar daya.
Kabel USB dan kabel adaptor terlihat terpasang pada sisi PCB.
Operator sebelumnya sudah mengonfirmasi **adaptor daya PCB
berbeda dari adaptor Raspberry Pi**, dan kabel USB untuk data
di antara kedua perangkat. Jalur kabel end-to-end tidak dapat
ditelusuri seluruhnya hanya dari dua foto, tetapi inventaris
USB Pi konsisten dengan perangkat FT232R.

**Penting:** foto hanya memperlihatkan panel/konektor dari
luar. **Chip FT232R, regulator, dioda/ideal diode/power mux,
pin USB VBUS dan routing PCB tidak terlihat**, sehingga tidak
boleh menyimpulkan proteksi backfeed sudah ada atau aman.
Label dan rangkaian **DB9** juga tidak diketahui; jangan
menghubungkan DB9 langsung ke GPIO 3,3 V Raspberry Pi.

Ini adalah **PCB custom target utama Smart Coffee**,
bukan **board Arduino Mega 2560 testbed** pada eksperimen
`bench/mega_pi_uart/`. Hasil uji TX/RX Mega testbed
tidak membuktikan keamanan/daya USB PCB custom ini.

## 2. Pemeriksaan aktual Raspberry Pi (tanpa membuka serial)

Pada Pi `enose-v3@enose-pi5` melalui SSH (read-only):

| Pemeriksaan | Temuan |
|---|---|
| USB device | FTDI FT232R, VID:PID `0403:6001` |
| USB serial | `A10KMM3S` |
| USB by-id | `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0` |
| Linux TTY | `/dev/ttyUSB0` via `ftdi_sio` |
| Descriptor konfigurasi | `bmAttributes = 0xa0` → **Bus Powered** / Remote Wakeup |
| Descriptor konsumsi | `MaxPower = 90mA` (nilai **deklarasi**, bukan hasil pengukuran) |
| Gejala undervoltage | `vcgencmd get_throttled = 0x0` saat pemeriksaan |
| USB serial-getty | inactive |
| Pemilik ttyUSB0 melalui fuser | tidak ditemukan pada snapshot |
| Kernel log yang difilter | `ftdi_sio` attached ttyUSB0; tidak ditemukan pesan overcurrent/undervoltage pada potongan yang diperiksa |

**Interpretasi:** USB descriptor FT232R mengaku
`Bus Powered` dengan konsumsi nominal yang dideklarasikan
90 mA, **bukan self-powered**. Ini dapat wajar bila
hanya chip USB bridge mengambil suplai host sedangkan
MCU/pompa/valve ditenagai eksternal. Tetapi itu
**tidak menunjukkan apakah jalur VBUS terhubung ke
rail 5 V sistem**, atau apakah ada backfeed/phantom powering.
Descriptor dan log perangkat **bukan pengukuran arus
atau verifikasi layout PCB**.

## 3. Riset sumber primer dan konsekuensi desain

1. **Raspberry Pi computer hardware — Back-powering dan USB maximum power**:
   https://www.raspberrypi.com/documentation/computers/raspberry-pi.html
   USB device tidak boleh memberi daya balik ke upstream host;
   back-power dapat melewati proteksi daya host.
2. **FTDI FT232R Datasheet, bagian 6.1 Bus Powered dan
   6.2 Self Powered Configuration**:
   https://ftdichip.com/wp-content/uploads/2020/08/DS_FT232R.pdf
   FT232R mendukung kedua desain; device self-powered tidak
   boleh memaksakan arus ke host ketika host dimatikan.
3. **Skematik custom PCB sendiri BELUM TERSEDIA** dalam
   repositori yang diperiksa. Karena itu belum bisa
   diverifikasi pemilihan suplai, diode/protection,
   power-off sequencing, USB VBUS/GND dan UART TX/RX.

**Risiko yang perlu diverifikasi:** cabang 5 V USB
terhubung ke suplai MCU tanpa pemilih/proteksi,
FT232 tetap bertenaga saat MCU off sehingga
memberi tegangan ke pin MCU lewat I/O (phantom powering),
atau MCU eksternal memberi arus balik ke host ketika
Pi off. Risiko ini **hipotesis engineering**, bukan
temuan kerusakan yang diamati di foto.

## 4. Gerbang verifikasi G0 yang dapat dikerjakan hardprog

1. **Foto/skematik sisi dalam PCB custom**: area konektor
   USB Type-B → chip FT232R/USB bridge → pin VBUS,
   serta konektor DC → regulator → rail 5 V MCU.
   Foto atas dan bawah/skematik lebih bermanfaat daripada
   foto panel luar, karena routing tidak tampak.
2. **Verifikasi skema** apakah FT232R benar USB bus-powered
   terpisah, MCU external-powered; cek kondisi satu perangkat
   mati dan yang lain hidup, grounding bersama, fuse/proteksi,
   serta kemungkinan I/O back-power ketika salah satu rail mati.
3. **Bila jalur daya belum jelas, pengukuran G0 oleh
   operator hardware berkompeten** memakai USB breakout/
   titik uji yang aman sesuai skema untuk memeriksa VBUS,
   isolasi, dan arus balik dengan Pi terputus dari PCB
   selama pengukuran. Jangan memasukkan probe telanjang
   ke konektor USB-B yang sempit, men-short VBUS–GND,
   melepas kabel berulang saat aktuator aktif, atau
   memotong jalur VBUS sembarangan (bridge bisa
   membutuhkannya untuk deteksi USB).
4. Setelah daya aman diverifikasi, operator menegaskan
   alat **IDLE**, pompa/valve tidak aktif, ada pengawasan
   langsung, dan risiko auto-reset DTR dapat diterima.
   **Mintakan izin G2 khusus** sebelum membuka port
   FT232R by-id secara read-only pada 115200 baud.
   G3 pengambilan data satu sesi melalui Nextion tetap
   memerlukan persetujuan terpisah.

| Gerbang | Status 13 Oktober 2026 |
|---|---|
| G0: identitas konektor, sumber daya, descriptor USB | **PARTIAL** |
| G0: skematik VBUS dan reverse-current/power sequencing | **BELUM TERBUKTI** |
| G1: kabel terpasang | **Dinyatakan/terlihat operator** |
| G2: USB serial opened/RX | **NOT RUN** |
| G3: satu sesi Nextion/pompa/valve | **NOT RUN** |
| Tahap 8 mock software sebelumnya | **PASS**, tidak menggantikan tes fisik |
| Mega testbed UART level shifter sebelumnya | **PASS**, sistem fisik berbeda |

**Tidak ada** opening ttyUSB0, reset MCU,
flashing, perintah Nextion, pompa/valve, atau
perubahan konfigurasi Pi selama audit foto ini.
