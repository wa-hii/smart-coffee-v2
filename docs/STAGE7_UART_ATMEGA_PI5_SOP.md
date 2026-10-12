# SOP Tahap 7 — UART ATmega2560 ↔ Raspberry Pi 5 (GPIO atau FT232)

**Tanggal:** 12 Oktober 2026. **Status:** pemetaan perangkat **PASS
read-only**; komunikasi fisik dan payload UART **BELUM TERVERIFIKASI**.
Dokumen ini menggantikan asumsi USB langsung dalam
`STAGE7_USB_ATMEGA_PI_BENCH_SOP.md` **hanya apabila** transport
yang dipakai benar-benar UART TTL. Tidak ada izin otomatis
untuk membuka port serial, mengubah firmware, mengaktifkan
aktuator atau melakukan akuisisi.

## 1. Hasil pemeriksaan Pi 5 melalui SSH

Host: `enose-v3@enose-pi5` (Tailscale). Firmware Raspberry Pi
memiliki:

| Objek | Bukti aktual, 12 Oktober 2026 |
|---|---|
| Native UART0 | `/dev/ttyAMA0`, `dtparam=uart0=on`, `dtoverlay=uart0-pi5` |
| GPIO14 | `TXD0`, dibaca dengan `pinctrl get 14` |
| GPIO15 | `RXD0`, dibaca dengan `pinctrl get 15` |
| Debug UART Pi 5 | `/dev/serial0 -> ttyAMA10`, **bukan** UART GPIO14/15 |
| USB-to-UART | FTDI FT232R, VID:PID `0403:6001`, driver `ftdi_sio` |
| Port adapter FT232 | `/dev/ttyUSB0`, by-id `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0` |
| Login serial getty | `inactive` untuk ttyUSB0/ttyAMA0/ttyAMA10 |
| Pemilik port yang tampak pada `fuser` | tidak terdeteksi saat pemeriksaan (tidak menjamin bebas selamanya) |
| Power Pi | `throttled=0x0` pada saat pemeriksaan |
| Status payload dari ATmega | **NOT TESTED**, port tidak dibuka |

Uji dapat diulang tanpa membuka port:

```bash
ssh enose-v3@enose-pi5
cd ~/smart-coffee-stage7
.venv/bin/python scripts/test_stage7_uart_preflight.py
.venv/bin/python scripts/stage7_uart_preflight.py
```

Perintah di atas hanya membaca filesystem dan menjalankan
`pinctrl get` (bukan `pinctrl set`).

## 2. Tentukan SATU jalur fisik sebelum menguji

**Jalur A — FT232R USB-to-TTL:** Pi USB ↔ FT232R ↔ UART ATmega.
Port calon `/dev/ttyUSB0` (gunakan by-id bila ada).
FT232R terdeteksi, tetapi keberadaan dongle **tidak**
membuktikan kabel TTL-nya benar-benar menuju ATmega.
Periksa tegangan logika FT232R sesuai papan/breakout:
**jangan menebak 3,3 V hanya dari identitas FT232R**.

**Jalur B — Pi GPIO UART0:** Pi GPIO14 TXD0, GPIO15 RXD0
↔ UART ATmega. Port calon `/dev/ttyAMA0`
(**bukan** `/dev/serial0` pada konfigurasi Pi 5 saat ini).
GPIO Pi hanya menoleransi sinyal logika **3,3 V**.
Jika ATmega menggunakan 5 V, TX ATmega → RX GPIO15 Pi
**harus melewati rangkaian penyesuaian level yang
diverifikasi**. TX Pi GPIO14 → RX ATmega juga perlu
dipastikan memenuhi spesifikasi input; rujuk skematik,
bukan asumsi. Wajib GND bersama dan TX→RX silang.
Jangan menghubungkan sinyal TTL ke pin power 5 V/3,3 V.

**Pilih satu cabang saja**. Jangan membuka ttyUSB0 dan
ttyAMA0 sekaligus atau menghubungkan dua output TX ke
satu RX. Jika routing aktual ambigu, STOP pada preflight.

## 3. Verifikasi sisi firmware ATmega sebelum membaca

Source firmware dalam repo saat ini memanggil
`Serial.begin(115200)` dan mengeluarkan frame ke
`Serial.print/println` (UART0 ATmega yang terhubung
ke interface USB/bootloader tergantung PCB). Jalur
`Serial2` digunakan oleh Nextion pada 9600 baud.
**Tidak ditemukan inisialisasi/pemancaran
`Serial1.begin/print` pada firmware yang diaudit.**

Pilih pin yang benar berdasarkan skematik board:

| UART ATmega | Nomor header Arduino Mega | Konsekuensi |
|---|---|---|
| USART0 `TX0/RX0` | D1/D0 | Kemungkinan mengeluarkan `Serial` 115200; **cek konflik jalur USB dan bootloader** |
| USART1 `TX1/RX1` | D18/D19 | **Belum mengeluarkan frame** karena Serial1 belum diaktifkan dalam source proyek |
| USART2 `TX2/RX2` | D16/D17 | Digunakan Nextion Serial2 9600, **jangan dipakai paralel** |
| USART3 `TX3/RX3` | D14/D15 | Belum menjadi jalur pengiriman data dalam firmware |

**PENTING:** header Arduino dan pin TQFP-100 MCU
adalah penomoran berbeda. Pemetaan di atas tidak
menjamin kesesuaian PCB custom. Firmware yang terpasang
pun belum dibuktikan sama dengan HEAD repo saat ini.

Jika kabel fisik berakhir di TX1/RX1, jangan
menyatakan baud 115200 sudah mengalir hanya karena
`/dev/ttyAMA0` atau FT232 tersedia. Perubahan
firmware untuk mengaktifkan Serial1 **memerlukan
persetujuan terpisah, pengujian regresi dan SOP flashing**;
tidak dilakukan dalam tahap preflight ini.

## 4. Gerbang izin hardware

- **G0 — keselamatan listrik:** operator fisik
  menyebutkan jalur A/B, pin ATmega, pin Pi/FT232,
  tegangan VCCIO/sinyal TX, level shifter jika
  memakai GPIO, GND bersama, PSU dan kondisi
  pompa/valve. Jika belum diverifikasi, **STOP**.
- **G1 — pemeriksaan pasif:** memastikan ID port,
  baud target, `fuser`, getty, suhu dan PSU.
  Ini bisa dikerjakan read-only tanpa izin
  membuka port.
- **G2 — izin membuka tepat satu port serial,
  hanya menerima:** setelah G0+G1 lolos
  dan pemilik perangkat memastikan kondisi
  aman. Pembukaan FT232 dapat memengaruhi DTR/RTS
  atau state reset via rangkaian ATmega.
  Tidak boleh ada `write()` atau `#start;`.
- **G3 — izin akuisisi via Nextion:** benar-benar
  terpisah karena pompa/valve dapat bergerak.
  Harus ada operator fisik dan observasi.

**Status sekarang:** G0 belum ada bukti skematik/
tegangan TTL; G2/G3 **TIDAK DIJALANKAN**.
Konfirmasi bahwa kabel sudah terpasang tidak sama
dengan validasi pin maupun izin G2.

### Addendum G0 — konfirmasi operator 12 Oktober 2026

Operator kini telah memastikan **jalur A: USB Pi → FT232R
USB-to-TTL**. Port FT232R di Pi sudah terenumerasi
(`ttyUSB0`, by-id), tetapi **port UART tujuan di
ATmega belum diketahui dan level tegangan sambungan
langsung belum diverifikasi**.

Dengan demikian: **jalur A terpilih, G0 BLOCKED, G1
fisik sudah terpasang menurut operator tetapi aspek
keamanannya belum tervalidasi, G2/G3 NOT AUTHORIZED**.
Keberadaan FT232R di bus USB **tidak mengungkap tegangan
VCCIO pada pin TX/RX modul FT232R**. Label `3V3/5V`
pada header atau jumper tertentu dapat merujuk pada
tegangan suplai, bukan selalu level logika data; identifikasi
modul/skematik yang tepat sebelum mengasumsikannya.

**Checklist wajib diselesaikan operator hardware sebelum
meminta izin G2:**

1. Foto jelas **kedua sisi FT232R** (tulisan pin
   `TXD/RXD/GND/VCC/3V3/5V`, jumper/solder bridge)
   dan koneksi FT232R ke header/PCB ATmega. Jangan
   memindah kabel selagi daya aktif.
2. Verifikasi dengan skematik/continuity **dalam keadaan
   semua sumber daya dimatikan secara aman**: FT232R
   RXD menerima TX dari USART ATmega yang mana
   (`TX0 D1` / `TX1 D18` / USART lain); FT232R
   TXD menuju RX yang sesuai, atau justru tidak
   digunakan; dan sambungan GND bersama.
3. Konfirmasi **tegangan logika MCU dan FT232R VCCIO**,
   sumber daya FT232R/ATmega, serta apakah VCC/VBUS
   FT232R terhubung ke rail 5 V board atau
   dapat memberi daya balik. Jika pengukuran
   tegangan perlu dilakukan saat aktif, hanya
   teknisi yang berwenang dengan alat ukur/probe
   aman; jangan mencoba-coba pada pin hidup.
4. Periksa tidak ada konflik dengan USB-serial
   on-board lain dan jalur Nextion USART2.
   Firmware repo hanya menerbitkan data di
   `Serial` / USART0 115200; USART1 belum
   dipakai untuk output. Jika terkoneksi ke
   USART1, masalahnya bukan baud semata.
5. Operator hardware catat `G0 PASS` **hanya**
   setelah pinout, level TTL, ground dan
   suplai/backfeed semuanya terverifikasi.
   Jika satu butir belum jelas, catat `BLOCKED`.

**Saat ini: STOP di G0.** Pemeriksaan
`udevadm`, `lsusb`, `fuser`, atau pemeriksaan
port lainnya bersifat read-only dan tidak
menggantikan bukti fisik. **Jangan menjalankan
`stage7_pi_adapter.py serial-readonly`, membuka
`/dev/ttyUSB0`, mengaktifkan Nextion,
atau flash firmware dulu.**

| Evidence G0 yang perlu dilampirkan | Status |
|---|---|
| Foto sisi depan/belakang FT232R + label pin | BELUM |
| Foto sambungan FT232R ke PCB ATmega | BELUM |
| Identitas UART ATmega (USART0/1/2/3) | BELUM |
| Tabel TX→RX dan ground terverifikasi | BELUM |
| FT232R VCCIO / level UART dan MCU VCC | BELUM |
| Risiko VBUS/backfeed terhadap PSU sensor/aktuator | BELUM |
| Kesesuaian pin dengan output `Serial` firmware | BELUM |
| Persetujuan operator hardware untuk G2 | BELUM |

## 5. Kandidat tes pasif setelah izin G2 (JANGAN JALANKAN SEKARANG)

Untuk **FT232 USB-to-TTL yang terbukti tersambung
ke UART0 ATmega** dan memiliki logika sesuai:

```bash
# HANYA SETELAH G0 dan G2 diberikan
cd ~/smart-coffee-stage7
.venv/bin/python scripts/stage7_pi_adapter.py serial-readonly \
  --port /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0 \
  --baud 115200 --duration 20 \
  --acknowledgment I_APPROVE_USB_SERIAL_READONLY \
  --output results/pi_stage7/uart_ft232_bench_run01.json
```

Adapter lama **sengaja menolak `/dev/ttyAMA0`**;
belum ada izin untuk memperluasnya. Jika ternyata
jalur GPIO Pi `ttyAMA0` yang dipakai, lakukan
review spesifik proteksi tegangan dan serial console
sebelum membuat runner native UART terpisah.

Saat MCU IDLE, frame sensor bisa memang tidak
dikirim. **Tidak melihat sampel saat IDLE bukan
bukti UART rusak**. Tanpa bukti trace UART,
status hanya `INCONCLUSIVE`, bukan PASS.

## 6. Kriteria keberhasilan dan penghentian

1. Identitas port dan pin fisik cocok (foto/skema dan pengukuran).
2. Tegangan sinyal sesuai; Pi GPIO tidak menerima TTL 5 V.
3. Satu pemilik port, login console tidak mengganggu.
4. Hanya frame JSON tervalidasi yang diterima di
   port yang telah disetujui, tanpa ada bytes dikirim
   dari Pi. State `AI_TEST` wajib tetap `N/A`.
5. Bila operator G3 mengizinkan Nextion,
   satu sesi lima siklus diobservasi
   (5 × purging 25 s dan collecting 5 s),
   termasuk urutan indeks/timestamp/terminal.
6. Jika terjadi restart, panas, PSU turun,
   pompa/valve tak sesuai, atau kabel
   tampak bermasalah: STOP oleh operator
   fisik, putus daya sesuai SOP alat,
   **jangan** melakukan reconnect otomatis.

**Tindakan yang tidak dilakukan:** flash firmware,
perubahan `/boot/firmware/config.txt`, restart
serial-getty/ModemManager, pengaturan GPIO,
skrip penggerak valve/pompa, implementasi
model AI, maupun transfer MCU→Nextion dari Pi.
