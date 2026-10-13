# Kondisi Aktual Smart Coffee E-Nose v2 — audit Tahap 0–1, 9 Oktober 2026

## Audit P2 firmware-runtime fingerprint — 13 Oktober 20:42–20:49 WIB

Dengan instruksi operator untuk melakukan diagnosis/perbaikan terukur,
dua capture tambahan yang **read-only** berhasil. Pada capture 15s,
14/14 frame sensor-shaped ditolak sebagai `invalid_phase`; pada
capture 8s berikutnya, diagnostik enum terbaru memastikan
**7/7 sensor-shaped berfase `idle`**, 0 event Nextion/akuisisi,
0 sampel valid. FT232R `A10KMM3S` tetap terenumerasi dan tidak
ada `USB disconnect` pada log boot baru. Semua capture dilakukan
tanpa TX ke MCU, START, flash, EEPROM atau aktuator dari Pi.

**Temuan provenance:** `git show 75cb38a^:src/main.cpp` menunjukkan
`adsCallback()` versi lama mengirim `printJsonData()` **setiap
callback, termasuk IDLE**. Source sesudah commit `75cb38a`
(9 Oktober) mengirim frame sensor hanya saat PURGING/COLLECTING.
Maka stream nyata saat IDLE konsisten dengan firmware pra-perbaikan,
tetapi **binary terpasang belum diidentifikasi**: kesimpulan versi
firmware masih hipotesis kuat, bukan verifikasi flash.

Adapter Pi kini menghitung kategori fase fixed-enum dan event
Nextion fixed-allowlist tanpa merekam nilai sensor atau nama
event arbitrer. Tes offline Windows dan Pi PASS; checksum adapter
terpasang cocok. G3 lima siklus **belum diulang**; harus ada
operator onsite yang memicu START via Nextion, preflight aman,
dan batas satu sesi dengan evidence baru. **G3 INCONCLUSIVE,
AI TEST tetap N/A, model NO-GO.** Laporan:
`docs/reports/2026-10-13_TAHAP7_P2_RUNTIME_FIRMWARE_DIAGNOSIS.md`.

## USB read-only 15s pasca-reboot — 13 Oktober sekitar 20:20 WIB

Dengan izin operator untuk satu capture IDLE, adapter **benar-benar
membuka** FT232R `A10KMM3S` 115200 selama 15 detik. Diterima
**5.026 byte, 44 chunk, 37 baris**: 23 JSON valid, 14 non-JSON;
14 JSON memiliki seluruh field `phase/cycle/sample_idx/timestamp`
dan 10 `adc_*`, tetapi **0** lolos validasi sampel aktif.
Key signature lain: 5 I2C found, 3 info, 1 scan done; **0 event
akuisisi**. `NOT_STARTED`/exit 2 adalah status validator saat IDLE,
**bukan** kegagalan membuka port. Raspberry Pi mengirim 0 byte TX.
Setelah capture, FT232R tetap terenumerasi, port bebas,
`throttled=0x0`, log boot tidak menunjukkan USB disconnect baru.

**Temuan kontrak:** source `src/main.cpp::adsCallback()` hanya
mengirim JSON sensor pada `purging`/`collecting`, bukan IDLE.
Adanya 14 JSON berbentuk sensor saat operator menyatakan IDLE
menguatkan kecurigaan perbedaan perilaku firmware terpasang,
tetapi nilai fase/indeks sengaja tidak direkam dan identitas
firmware belum terbukti. Jangan menyimpulkan akar masalah pasti.
Host kini memiliki diagnostik offline `sensor_like_invalid_frames_by_reason`
berbasis kode alasan statis tanpa nilai ADC; **hasil capture ini
tidak dapat direklasifikasi dari metadata historis**.
G3 masih INCONCLUSIVE, AI NO-GO.
Laporan: `docs/reports/2026-10-13_TAHAP7_P1_USB_IDLE_SCHEMA_15S_RESULT.md`.

## Audit independen pasca-reboot — 13 Oktober 20:09–20:12 WIB

Pemeriksaan **baru langsung melalui SSH dengan host key diverifikasi**:
`uptime -s=2026-10-13 19:49:19`, FT232R `0403:6001` serial
`A10KMM3S` terenumerasi di Bus 003 Device 002 dan by-id mengarah
ke `/dev/ttyUSB0`. `ftdi_sio` aktif, `fuser` tidak menemukan
pemilik port, getty/ModemManager inactive, `throttled=0x0`.
Pemeriksaan ulang 20:12 WIB tetap menemukan FT232R; tidak ada
pesan `USB disconnect` pada log kernel boot baru yang diperiksa.
Ini **PASS enumerasi pasif pada dua titik waktu**, **bukan**
sertifikasi stabilitas saat port dibuka maupun selama G3.

Checksum `stage7_pi_adapter.py` lokal dan Pi sama:
`5628304575b3d28d2234106b5f198e8670614b82301174206429df2b`.
Checksum evidence G3 Run02 Pi masih sama dengan laporan asli:
`9a6733326df5f941110433dc888bb25dede37a10ec8df7db6070ea461a6dec20`.
Regresi Stage 7 Bridge/Adapter/USB Probe dan Stage 8 offline
**PASS Windows dan Pi**; build `mega2560`/`nextion_test`, kontrak
HMI, Stage 1, Stage 6 juga **PASS offline Windows**.
**G3 tetap INCONCLUSIVE, AI release NO-GO.** Tidak ada serial
open, perintah MCU, reboot, flashing atau pengujian fisik baru.
Laporan: `docs/reports/2026-10-13_TAHAP7_P0_REAUDIT_POST_REBOOT.md`.

## Setelah reboot Raspberry Pi oleh operator — 13 Oktober 19:50 WIB

Operator memberi tahu Raspberry Pi kembali menyala.
SSH ke `enose-pi5` berhasil; `uptime -s` menunjukkan
**boot baru pada 19:49:19 WIB**. FT232R
`0403:6001`, serial `A10KMM3S`, **berhasil
terenumerasi kembali** pada 19:49:22:
`/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`
→ `/dev/ttyUSB0`. Driver `ftdi_sio` aktif,
`fuser` tidak mendeteksi pemilik port,
`serial-getty` dan `ModemManager` inactive,
Pi `throttled=0x0`.

**Status USB enumeration RESTORED (PASS pasif).**
Belum ada pembukaan port serial atau JSON yang
diverifikasi setelah reboot; USB transport,
hardware G3, dan kesesuaian firmware dengan
kontrak sensor masih memerlukan pengujian
terpisah. Reboot menyelesaikan gejala hilangnya
enumerasi, tetapi tidak membuktikan akar masalah.
Jangan lakukan auto-open atau auto-G3 tanpa
persetujuan tambahan.

## Reboot Raspberry Pi diminta operator — 13 Oktober 19:47 WIB, BLOCKED

Operator mengizinkan restart **Raspberry Pi 5**
untuk mencoba pemulihan enumerasi FT232R.
Preflight SSH `enose-pi5`: tidak ada
listener/akuisisi serial aktif, FT232R
belum terlihat di `lsusb` atau `ttyUSB*`,
`get_throttled=0x0`, uptime Pi masih
berasal dari boot `14:24 WIB`.
`sudo -n -v` ditolak (`a password is
required`), lalu `systemctl --no-ask-password
reboot` ditolak (`Interactive authentication
required`). **Tidak ada reboot aktual**,
tidak ada percobaan melewati autentikasi
atau mengubah sudo/polkit.
Operator perlu menjalankan `sudo reboot`
sendiri dari terminal Pi dengan autentikasi
setempat. Setelah Pi menyala, ulangi
**enumerasi USB pasif**, tanpa membuka
UART/AI TEST.

## Setelah restart operator — cek USB pasif 19:41 WIB

SSH Pi berhasil, tetapi FT232R `0403:6001`
**tetap hilang** dari `lsusb`;
`/dev/ttyUSB0`/by-id tidak tersedia.
USB root hub normal, `throttled=0x0`,
log kernel berakhir pada disconnect
`19:24:44` tanpa enumerasi berikutnya.
Pi `uptime -s=14:24:00` sehingga tidak
terlihat reboot setelah disconnect;
jenis perangkat yang di-restart oleh
operator belum dikonfirmasi.
Tidak dilakukan serial open atau
restart USB host. Status **BLOCKED**.

## Pasca USB disconnect: konfirmasi operator & Pi (19:33 WIB)

Operator mengonfirmasi **PCB custom dan
Nextion tetap menyala normal**, kabel
USB tetap terpasang pada kedua sisi.
Pemeriksaan **pasif** SSH Pi: USB
root hub normal tetapi FT232R
`0403:6001` `A10KMM3S` **tidak
terenumerasi**, `/dev/ttyUSB0` dan
sysfs `3-1` tidak ada, kernel
terakhir mencatat disconnect
**19:24:44 WIB**, `throttled=0x0`.
Tidak ada serial open/retry.
**STOP uji G3/serial** sampai
inspeksi kabel, konektor, jalur
USB dan daya FT232R sesuai SOP.
Rujukan:
`docs/reports/2026-10-13_TAHAP7_USB_READONLY_15S_DISCONNECT.md`.

## USB 15s read-only 13 Oktober malam — BLOCKED/DISCONNECTED

Operator mengizinkan pembacaan hanya 15s
untuk memeriksa skema JSON tanpa START.
Preflight Pi PASS: FT232R `A10KMM3S`/
`ttyUSB0` hadir, tidak dipakai proses lain,
script hash tepat, offline regression PASS.
Saat port dibuka, muncul `SerialException
Errno 19: No such device`; kernel mencatat
`usb 3-1: USB disconnect` **19:24:44 WIB**
dan gagal konfigurasi FTDI.
Pasca-percobaan USB tidak terenumerasi,
port sudah hilang, output 15s tidak dibuat,
dan tidak ada JSON masuk/perintah Pi.
`get_throttled=0x0` pada Pi; ini
tidak memverifikasi power PCB.
**Tidak ada retry otomatis.**
Status G3 tetap INCONCLUSIVE dan
pemeriksaan fisik/USB G0 harus
dilakukan sebelum izin open ulang.
Laporan:
`docs/reports/2026-10-13_TAHAP7_USB_READONLY_15S_DISCONNECT.md`.

## Update diagnosis G3 Run02 — 13 Oktober 2026 malam

Operator **sudah menekan START AI TEST** dan
**melihat lima siklus sampai selesai** pada
Nextion selama Run02. Oleh karena itu
hipotesis START tidak ditekan tidak lagi
menjadi penjelasan untuk `NOT_STARTED`
host. Run02 tetap menerima 189 JSON valid
tetapi 0 event/sampel yang sesuai kontrak.
Source firmware memang mendefinisikan event
`ACQ_START`/`PHASE_CHANGE`/`ACQ_COMPLETE`
dan 10 key ADC, tetapi **kesesuaian firmware
terpasang belum diketahui**; isi 189 JSON
tidak disimpan di file lama.

Diagnostik metadata `other_json_key_signatures`
telah ditambahkan ke listener untuk
**uji berikutnya dengan izin baru**:
field name/count saja, tanpa sensor values,
label, perintah MCU atau auto-test.
Kode baru telah dideploy ke Pi dan
regresi `test_stage7_pi_adapter.py`
serta `test_stage7_bridge.py`
**PASS offline pada Pi**.
G3 Pi **INCONCLUSIVE**; belum ada
pengujian hardware ketiga.
Lihat addendum
`docs/reports/2026-10-13_TAHAP7_G3_NEXTION_RUN02_RESULT.md`.

## G3 USB Run02 langsung pada Pi — 13 Oktober 2026

Listener `stage7_pi_adapter.py` versi
reassembly baru telah diverifikasi
SHA256 identik Windows/Pi; semua
regresi offline PASS di kedua host.
G3 satu kali ulang dijalankan di
Pi dengan port FT232R 115200 selama
180s. **52.224 byte / 303 chunk /
203 baris lengkap** diterima; ada
**189 JSON valid**, 14 non-JSON,
tetapi **0 event START/COMPLETE,
0 sampel cocok skema, terminal 0**.
Validator tetap `NOT_STARTED/N/A`,
exit 2; port sesudah uji tertutup
dan power `throttled=0x0`.
Jadi bug fragmentation sebelumnya
sudah diperbaiki, tetapi **belum
cukup untuk E2E G3 PASS**.
Perlu konfirmasi apakah START ditekan
dan lima siklus selesai pada Run02;
bila ya, diagnosis lanjut harus
memeriksa struktur field JSON
firmware aktual, bukan mengklaim
189 JSON sebagai sampel.
Laporan:
`docs/reports/2026-10-13_TAHAP7_G3_NEXTION_RUN02_RESULT.md`.

## Koreksi G3 dan framing Pi — 13 Oktober 2026

Operator mengonfirmasi **START AI TEST sudah ditekan
ketika listener Pi aktif dan lima siklus terlihat
berjalan di LCD Nextion**. Maka hasil lama
`NOT_STARTED` adalah **gagal deteksi sisi Pi**,
bukan bukti bahwa fisik akuisisi tidak berjalan.
File asli G3 (304 nonempty reads, 0 terminal)
tetap utuh; tidak tersedia rekaman raw per frame
untuk menghitung sampel sesi tersebut.

Ditemukan bug source: pemanggilan `read_until`
dengan timeout 1s bisa memecah satu pesan JSON;
parser lama menganggap potongan tersebut
pesan lengkap. `SerialLineFramer` dan
`receive_serial_chunks` kini merakit ulang
pesan sampai LF dengan batas 4096 byte dan
diagnostik event/sampel tanpa raw sensor.
Regresi Windows **PASS** termasuk 151 sampel
replay asli. **G3 hardware masih INCONCLUSIVE**,
belum diulang; tidak ada model yang dirilis.
Laporan:
`docs/reports/2026-10-13_TAHAP7_G3_UART_RX_FRAMING_FIX.md`.

## G3 Nextion PCB custom — 13 Oktober 2026, INCONCLUSIVE

Operator mengizinkan **satu sesi G3** via
Nextion, pengguna diminta menekan
START AI TEST setelah listener aktif.
Listener Pi FT232R 115200 berjalan
maksimal 180s dan selesai dengan
`final.quality=NOT_STARTED`,
`reason=no_completed_session`;
ada **304 nonempty serial read chunks**
tetapi **tidak ditemukan event ACQ_START
valid atau terminal akuisisi**. Ini
**bukan 304 sampel sensor**.
Port ditutup tanpa perintah Pi;
get_throttled sesudah tes `0x0`.
Tidak ada bukti sesi lima siklus
diselesaikan. **Jangan menganggap
G3/E2E PASS**. Perlu konfirmasi
apakah START ditekan di Nextion
dan apakah alat benar-benar
menjalankan lima siklus sebelum
merancang retry.
Evidence asli ada di Pi;
laporan:
`docs/reports/2026-10-13_TAHAP7_G3_NEXTION_RUN01_INCONCLUSIVE.md`.

## Konfirmasi pasca-G2 — 13 Oktober 2026

Operator menyatakan **"alat tetap normal
seperti biasanya"** setelah uji USB
read-only 12 detik pada PCB custom.
Ini **observasi operasional yang positif**,
namun tidak membuktikan tidak ada
auto-reset MCU sesaat. USB transport
G2 **PASS**, classifier/JSON
**PARTIAL**, data sampel belum
terbaca karena sistem IDLE.
**G3 yang dapat menggerakkan
pompa/valve belum dijalankan dan
memerlukan persetujuan terpisah**.
Bukti dan interpretasi:
`docs/reports/2026-10-13_TAHAP7_G2_USB_LIVE_RESULT.md`.

## HASIL G2 LIVE USB PCB custom — 13 Oktober 2026

Operator menyatakan alat menyala namun **IDLE**
(tidak sedang akuisisi), dan menyetujui
pembukaan USB FT232R 12s termasuk risiko
auto-reset. Probe `scripts/stage7_usb_readonly_probe.py`
**BENAR-BENAR MEMBUKA** by-id `A10KMM3S`
→ `ttyUSB0` pada **115200** dan menerima
**4.313 byte / 33 baris**:
`other_json=14`, `i2c_found=5`,
`i2c_scan_done=1`, `invalid_json=13`.
Frame sensor aktif **0**;
**tidak ada byte/perintah TX dari Pi**,
operasi aktuator, atau inferensi model
yang dijalankan oleh probe.

Transport USB physical **PASS**,
validasi seluruh payload **PARTIAL**.
13 baris non-JSON diduga setidaknya sebagian
dari `printWelcome()` yang menulis banner
plain text, belum terverifikasi baris per
baris karena evidence hanya hash.
I2C scan/startup konsisten dengan
aktivitas inisialisasi/reset, tetapi
reset oleh DTR tidak terbukti langsung.
Sampel 0 konsisten dengan source
`adsCallback()` yang hanya kirim
sampel ketika state akuisisi aktif.
G3 dan produksi AI **NOT RUN/NO-GO**.
Laporan dengan hash evidence:
`docs/reports/2026-10-13_TAHAP7_G2_USB_LIVE_RESULT.md`.

## Progres G2 USB PCB custom — 13 Oktober 2026

Pembuat PCB menyatakan **rangkaian custom aman**;
dicatat sebagai attestation operator (belum ada
ukur independen untuk VBUS/backfeed).
FT232R `0403:6001` `A10KMM3S` masih
terenumerasi di `/dev/ttyUSB0` pada Pi,
port tidak terlihat digunakan, getty
dan ModemManager inactive, throttled 0x0.
Source firmware `Serial` host 115200,
`Serial2` Nextion 9600, `actuator.begin()`
memanggil stop() jika source ini yang
terpasang di device; deployed firmware
belum diverifikasi.
Probe `scripts/stage7_usb_readonly_probe.py`
berhasil lolos tes Windows+Pi,
telah dideploy ke Pi dengan batas
12–30s, parser newline incremental,
hash metadata dan no-serial-write.
**G2 live NOT RUN** sampai alat
IDLE, ada pengawas onsite,
dan persetujuan G2/reset.
**G3 NOT RUN, AI NO-GO**.
Laporan `docs/reports/2026-10-13_TAHAP7_G2_USB_PROBE_READY.md`.

## Audit foto USB PCB custom pada Pi — 13 Oktober 2026

Foto operator memverifikasi panel **PCB custom** dengan
USB Type-B, DB9, sakelar dan adaptor DC eksternal;
foto Pi 5 memperlihatkan USB-A data, USB-C power,
serta fan. SSH read-only Pi: FT232R `0403:6001`
terdeteksi `ttyUSB0` dengan nomor serial
`A10KMM3S`, descriptor USB `bmAttributes=0xa0`
**Bus Powered** dan `MaxPower=90mA`
(deklarasi bukan konsumsi terukur),
`throttled=0x0`, getty inactive,
fuser port kosong saat diperiksa.
Foto panel tidak menampakkan jalur daya
VBUS/rail eksternal/chip USB/regulator:
**G0 partial/belum PASS, G2 & G3 NOT RUN**.
Eksperimen sukses Arduino Mega Serial1
↔ Pi GPIO sebelumnya adalah testbed
berbeda dan tidak memverifikasi PCB custom.
Lihat `docs/reports/2026-10-13_AUDIT_FOTO_USB_PCB_CUSTOM_G0.md`.

## UART testbed Mega↔Pi SUKSES — 12 Oktober 2026

Koreksi laporan sebelumnya: setelah operator
menukar HV1→Mega D18 **TX1** dan
HV2→Mega D19 **RX1**, UART RX Pi mulai
menerima byte mentah valid. Validator
awalnya salah mendeteksi ~40 frame
rusak per 20s karena membaca baris
parsial pada timeout 0,5s sedangkan
heartbeat hanya 1 Hz. Parser diperbaiki
menjadi buffer incremental bounded
hingga newline.

**PASS_RX_ONLY** 5 heartbeat berurutan
0 error; **PASS_BIDIRECTIONAL** 5
heartbeat dan 1 PONG nonce benar,
diverifikasi bersamaan dengan USB
debug Mega **1 PING ACK**. Uji
stabilitas duplex 30 s
**PASS 28 heartbeat, 1 PONG,
0 malformed/gap/duplikasi**.
Semua uji ini **hardware testbed
Arduino Mega 2560 + level converter +
GPIO UART0 Pi** pada 9600 baud,
bukan firmware PCB custom/Nextion
atau model AI Smart Coffee. Bukti
`bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`.

## UART testbed terpisah Mega↔Pi, 12 Oktober 2026

Testbed **Arduino Mega 2560 board sementara**
(bukan PCB custom target Smart Coffee)
sekarang punya proyek mandiri
`bench/mega_pi_uart/`, firmware
`Serial1` 9600 pada Mega D18/D19
dan Python Pi `/dev/ttyAMA0`
GPIO14/15. Firmware berhasil
di-upload COM6 CH340 ke chip
ATmega2560 (signature 0x1e9801),
USB debug heartbeat 1–19 terbaca
dari Mega. Namun RX Pi 20 detik
**0 frame** dan satu PING diagnostik
Pi menghasilkan **0 PING ACK** pada
debug Mega. Pi sudah UART0 ALT aktif,
getty inactive, port bebas dan power
`throttled=0x0`.

**Kondisi UART testbed: BLOCKED hardware
level converter/wiring/pinout belum
diverifikasi operator dengan foto
atau tegangan.** Tidak boleh klaim
E2E hardware PASS; jangan memindah
jumper dalam keadaan menyala.
Laporan dan data asli:
`bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`,
`bench/mega_pi_uart/evidence/`.
Pekerjaan Smart Coffee firmware PCB custom
tetap pada status yang terpisah.

## Keputusan riset USB dan E2E offline — 12 Oktober 2026

Dokumentasi resmi Raspberry Pi membolehkan
periferal USB dengan daya sendiri (arus
USB total Pi 5 600 mA/1,6 A bergantung
PSU), dan FT232R mendukung konfigurasi
self-powered. **Namun, desain USB VBUS
PCB custom ATmega dengan adaptor eksternal
belum diverifikasi untuk reverse-current/
backfeed.** SSH read-only menemukan
FT232R `ttyUSB0`, `usb_max_current_enable=1`,
`throttled=0x0`, tanpa error overcurrent
di potongan log yang difilter; bukti ini
tidak cukup untuk meluluskan G0.
**Tidak membuka port USB serial.**

Tahap 8 **OFFLINE MOCK PASS 11/11** pada
Windows dan Raspberry Pi, input data riil
`D-GAW_B33.csv` (151 frame):
dua jalur positif dan sembilan fault
FAIL_CLOSED; autosave labeled-data diuji
151/151 hanya di memori. Hasil AI tetap
`N/A`, mock Nextion **bukan UI nyata**,
tidak ada model/aktuator dipanggil.
Tahap 9 hardware dan 10 AI rilis
**NO-GO / NOT TESTED**. Laporan
`docs/reports/2026-10-12_RISET_USB_PI5_DAN_E2E_TAHAP8.md`.

## Addendum daya ATmega dan Pi (12 Oktober 2026)

Operator memastikan **Raspberry Pi 5 memakai adaptor
daya sendiri, ATmega2560 memakai adaptor eksternal
yang berbeda**, serta komunikasi USB langsung
ATmega→Pi. Rangkaian VBUS FT232R, pemilihan daya
USB/eksternal, board custom vs Mega resmi, jalur
adaptor (DC jack/VIN atau 5 V langsung), dan
backfeed **belum diverifikasi**. Status:
**G0 PARTIAL/BLOCKED**, G1 USB telah dipasang
menurut operator, **G2 serial RX dan G3
akuisisi NOT AUTHORIZED/NOT RUN**.
SOP dan checklist:
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.
Tidak ada pembukaan serial, perintah MCU,
atau modifikasi power pada langkah ini.

## Transport USB yang sebenarnya — 12 Oktober 2026

Operator menegaskan kabel **USB port ATmega
langsung ke port USB Raspberry Pi**;
tidak menggunakan GPIO maupun kabel TX/RX
TTL eksternal. Pi mendeteksi FT232R sebagai
`/dev/ttyUSB0`, by-id
`usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`.
Source firmware: `Serial`/UART0 115200
untuk data host; `Serial2` (Mega RX2 D17/
TX2 D16) 9600 untuk Nextion; `Serial1`
kosong. FT232R yang terdeteksi dapat
merupakan jembatan serial board,
namun pencocokan PCB/skematik belum
terverifikasi.

**G1 kabel terpasang (pernyataan operator),
G0 keselamatan VBUS/power belum disetujui,
G2 membuka serial dan G3 akuisisi NOT RUN.**
Tidak perlu level shifter GPIO Pi untuk
kabel USB standar; risiko backfeed 5 V
dan reset DTR tetap perlu diaudit.
SOP aktif `docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.

## Gerbang G0 FT232 → ATmega — 12 Oktober 2026

Operator menegaskan jalur USB Pi → FT232 USB-to-TTL;
`/dev/ttyUSB0` terdeteksi tetapi USART ATmega
dan logika sambungan langsung **belum diketahui**.
Tidak ada skematik atau foto wiring yang cukup
dalam repo untuk memvalidasi VCCIO, TX/RX, GND,
dan risiko daya balik. **G0 BLOCKED,
G2/G3 NOT AUTHORIZED; tidak membuka ttyUSB0**.
Checklist lanjutan pada
`docs/STAGE7_UART_ATMEGA_PI5_SOP.md`.

## Temuan UART Pi terbaru — 12 Oktober 2026

Pi 5 `enose-pi5` diakses dengan SSH
read-only. Ada FT232R USB-to-UART
`/dev/ttyUSB0` dan native GPIO14/15
UART0 `/dev/ttyAMA0` yang aktif;
`/dev/serial0 -> ttyAMA10` merupakan
debug UART Pi 5. Board FT232 terenumerasi,
tetapi koneksi kabel TTL ke ATmega
**belum terbukti**. Firmware aktif repo
masih mengirim ke ATmega `Serial` 115200,
bukan `Serial1` D18/D19. Tegangan
UART/level-shifter dan pemetaan pin
harus diverifikasi bersama operator.
**Port belum dibuka**, tidak ada
flash/servo/valve/Nextion command.
Detail `docs/reports/2026-10-12_TAHAP7_UART_PI5_PREFLIGHT.md`.

## SOP USB bench siap review — 11 Oktober 2026

`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`
memisahkan pemeriksaan catu dan VBUS USB (G0),
izin pemasangan kabel (G1), izin membuka serial
read-only (G2), serta izin menggerakkan aktuator
melalui satu sesi Nextion (G3). **Tidak ada
yang dieksekusi**. Adapter serial Pi sekarang
menggunakan buffer serial berukuran terbatas
dan advisory exclusive lock Linux, diuji
menggunakan stub serial tanpa port fisik.
Tahap 7 software/SSH/replay masih PASS,
USB live **NOT TESTED**, model AI **NO-GO**.

## Status terbaru Tahap 7 — SSH dan replay nyata di Pi (11 Oktober)

SSH `enose-v3@enose-pi5` melalui Tailscale
berhasil; Pi 5 Rev 1.1/Debian 13/Python 3.13.5
terverifikasi. Venv terisolasi
`~/smart-coffee-stage7/.venv` disiapkan hanya
dengan `pyserial==3.5`. Runner
`scripts/stage7_pi_adapter.py` diuji langsung
pada Pi bersama regresi bridge dan preflight:
**PASS**. Replay data asli
`D-GAW_B33.csv` menghasilkan 151 sampel,
`COMPLETE_QA`, hasil AI `N/A`,
tanpa membuka serial atau mengirim perintah
aktuator. SHA256 data asli host dan Pi sama.

**ATmega tidak tersambung**, tidak ada port
`ttyACM/ttyUSB` dan tidak ada proses/service
adapter yang menetap. Status model Tahap 6
tetap NO-GO. Detail:
`docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`.

## Addendum Tahap 7 (10 Oktober 2026)

Operator menyatakan ATmega **tidak dikoneksikan ke COM5**,
sedangkan Raspberry Pi 5 sudah menyala agar bisa diremote.
Belum ada alamat dan username SSH Pi yang dapat digunakan,
sehingga **status remote Pi belum terverifikasi**.
Tidak ada perangkat serial/USB Pi–ATmega yang diuji
dan tidak ada akses COM5, flashing atau perubahan GPIO.

Adapter host `scripts/stage7_bridge.py` plus regresi
`scripts/test_stage7_bridge.py` menyiapkan sesi dan
parser legacy read-only, penjaga envelope v1
serta ACK/NACK simulasi, replay CSV asli tanpa label
dan output AI_TEST **N/A**; tidak dapat mengirim hasil
ke firmware lama. `scripts/stage7_pi_preflight.py`
menyediakan inventaris read-only ketika target SSH
tersedia. Transport USB 115200 diprioritaskan sebagai
kandidat, UART1 GPIO memerlukan level shifter dan
verifikasi PCB (Pi5 debug UART berbeda).
SOP `docs/STAGE7_PI_REMOTE_AND_SERIAL_SOP.md`,
laporan `docs/reports/2026-10-10_TAHAP7_PI_INTEGRATION_PREP.md`.

## Addendum 10 Oktober 2026 — dataset asli dan gerbang Tahap 6

Unduhan Zenodo DOI `10.5281/zenodo.15425922` CoffeePow-4
dan Aroma-7 **lulus MD5 penerbit dan SHA256**. Jumlah
rangkaian lengkap adalah **3.583** dan **4.750**;
seluruh CoffeePow-4 terkandung identik di Aroma-7
(tidak independen), sementara empat pembacaan terakhir
Aroma-7 tidak membentuk rangkaian lengkap dan ditahan.
Benchmark RF CoffeePow-4 empat kelas mendapat macro-F1
**0,906 split acak** vs **0,501 split urutan akhir
per kelas**; ini *bukan* hasil pada alat lokal.
Data BME688 tidak menambah 83 sampel kopi MQ/TGS kita.

Gerbang `scripts/stage6_release_gate.py` menghasilkan
`model_promotion_allowed=false`, AI_TEST `N/A`.
Tahap 5 ilmiah tetap **NO-GO**, Tahap 6 **hanya
persiapan gerbang offline**, belum model final/deployment.
Lihat `docs/reports/2026-10-10_RISET_DATASET_EKSTERNAL_DAN_TAHAP6.md`.

## Pembaruan terbaru — koreksi CAW dan Tahap 4 (9 Oktober 2026)

### Tahap 5 — penilaian unknown (9 Oktober)

Analisis offline tambahan di `results/stage5_validation_v1/`:
RF82 dan LDA10 masing-masing memiliki **45/83 benar**, **38/83
salah** pada prediksi out-of-fold kopi kandidat. Keduanya memprediksi
**light roast pada lima dari lima uji udara bersih yang lolos QA**;
ambang 0,6 tidak menolak satu pun. Pada confidence 0,8,
RF menerima 9 sampel dengan 3 salah; LDA 20 dengan 6 salah.
**Status unknown NO-GO**; jangan gunakan model roast-only untuk
menyatakan medium terdeteksi kopi. Bootstrap hanya 4 cluster,
simulasi gain bukan tes fisik. Detail:
`docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.

Operator mengonfirmasi **CAW dan seluruh batch B37 adalah udara bersih**.
Empat CAW B33–B35 dan dua CSV B37 kini dinyatakan bukan kopi,
dikecualikan berdasarkan nama serta SHA256, tanpa mengubah data asli.
`data/analysis/stage2_v2/` dan `data/processed/stage3_v2/` adalah
snapshot canonical baru untuk **83 kandidat file kopi B32–B35**, bukan
snapshot lama 87/86 yang memuat CAW.

Benchmark Tahap 4 secara offline: 7 grup × 8 model × 4 batch LOBO,
224 kombinasi fit/fold; macro-F1 rerata tertinggi deskriptif RF
expanded82 **0,490**, hampir setara LDA response10 **0,482**.
**Tidak ada model final/hasil validasi prospektif.** Identitas spesimen
fisik, label roast dan perbedaan batch tetap perlu audit; lihat
`docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.

> Sumber acuan: kode sumber, hasil QA offline, dan CSV mentah B32–B35 pada direktori utama. Dokumen ini mencatat keadaan rekayasa yang telah diperiksa, **bukan bukti pengujian perangkat fisik secara langsung**.

## 1. Repositori dan ruang lingkup

- Repositori kerja: smart-coffee-v2-hardware/smart-coffee-v2-hardware, branch **wahyu**. Baseline awal audit independen 8 Oktober adalah **54d3321**; baseline sebelum audit Tahap 0 tanggal 9 Oktober adalah **bf7080e**. Perubahan lokal `platformio.ini` untuk COM5 tetap milik pengguna dan tidak dimasukkan ke commit.
- Firmware utama ATmega2560 berada di **src/**. Proyek HMI Nextion yang menjadi acuan adalah **nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI**. Aset desain Figma telah dikunci; berkas TFT lama belum terbukti identik dengan HMI terbaru.
- Urutan sensor pada firmware dan CSV: TGS822, MQ135, **MQ3**, TGS2611, TGS2620, TGS2600, TGS2602, MQ8, TGS813, TGS816. Empat ADS1115 menggunakan alamat 0x48–0x4B; SHT30 dibaca melalui bus I2C.
- Nextion: USART2 (`Serial2`) 9600 baud, yaitu PH0/RXD2 pada **pin TQFP-100 nomor 12** (RX2/D17 pada header Arduino Mega) dan PH1/TXD2 pada **pin nomor 13** (TX2/D16). Angka pin IC 8/9 pada dokumen lama keliru menurut datasheet Microchip. Serial USB ke komputer/host menggunakan 115200 baud. Koreksi belum diverifikasi pada skematik PCB fisik.
- Akuisisi aktif: **5 siklus × (purging 25 detik + collecting 5 detik)**, dengan durasi nominal sekitar 150 detik per pengujian. Keterlambatan antarmuka/komunikasi dan durasi nyata masih harus diukur.

## 2. Kondisi dan kesiapan subsistem

| Subsistem | Bukti yang telah diperiksa | Hal yang belum dibuktikan |
|---|---|---|
| Firmware utama ATmega | Kompilasi PlatformIO mega2560 berhasil. RAM statis 3.720/8.192 byte dan flash 35.854/253.952 byte pada saat pemeriksaan. | Pembacaan sensor fisik, ketepatan waktu, stack/heap runtime, pemanasan sensor, kalibrasi, dan keselamatan aktuator. |
| Firmware uji Nextion | Kompilasi environment nextion_test berhasil. | Pertukaran UART nyata, pemulihan koneksi, dan penanganan galat perangkat. |
| HMI | Pemeriksa offline berhasil untuk 12 aset Figma, 12 halaman HMI, 23 event yang dipetakan, serta kontrak komunikasi. | Kompilasi Nextion Editor, simulasi editor, TFT terbaru, dan layar fisik. |
| Akuisisi | 87 dari 87 CSV B32–B35 yang terlihat pada mesin ini (9 Oktober, setelah run baru) lolos validator struktur. | Keakuratan kalibrasi ADC/sensor, timing fisik valve, dan identitas spesimen/sesi. |
| Ekstraksi fitur | Kandidat 62 fitur dengan 86 observasi tingkat file berhasil dibuat tanpa training. | Seleksi fitur ilmiah, uji generalisasi, dan kesesuaian fitur ketika inferensi. |
| Model AI | Laporan historis Random Forest B01–B05 tersedia. | Evaluasi, pemilihan, serta validasi model pada B32–B35. |
| Raspberry Pi 5 | Menjadi target integrasi yang direncanakan. | Implementasi adapter, benchmark pada Pi, dan komunikasi inferensi dua arah. |

**Audit Tahap 0 (9 Oktober):** baseline lintas modul dicatat di `docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`. Script `scripts/test_stage0_contract.py` memeriksa konstanta fase, kanal ADC, format serial/CSV, sumber HMI, pemetaan preset antar-kolektor, serta pemetaan pin Nextion tanpa mengakses COM5. Opsi UART `Serial1` ke Raspberry Pi masih rancangan, bukan jalur yang telah dipasang atau aktif.

## 3. Inventaris dataset B32–B35

**Snapshot dasar 8 Oktober 2026 (86 file)** dicantumkan di bawah untuk membedakan hasil audit sebelumnya dari data yang masuk kemudian:

- Total **86 berkas**: B32 = 18; B33 = 20; B34 = 22; B35 = 26.
- Total **13.615 baris CSV**: **13.003 baris sensor lengkap** serta **612 baris event historis yang hanya berisi metadata**. Tidak ditemukan baris sensor parsial menurut validator struktural.
- Distribusi fase: **10.756 baris purging** dan **2.247 baris collecting**.
- Tidak ditemukan nilai suhu atau kelembapan yang hilang pada himpunan data ini. Tidak ditemukan sel ADC bernilai 0 atau 32767.
- Distribusi file berdasarkan tingkat roasting: light = 30; medium = 28; dark = 28. Ditemukan **23 kombinasi kode sampel roast–origin**.
- Secara nominal terdapat 430 kelompok siklus (86 × 5), **bukan 430 spesimen kopi fisik yang independen**. Beberapa file B35 dengan akhiran timestamp adalah pengukuran tambahan; independensinya belum diketahui.
- Field timestamp berasal dari **millis() ATmega**, yakni waktu sejak MCU menyala, bukan tanggal dan jam kalender. CSV aktif belum menyertakan ID spesimen fisik, ID sesi atau tanggal pengukuran yang eksplisit.
- Definisi identitas origin perlu dibakukan, terutama kode **TEM/MUK** yang memiliki variasi nama pada metadata historis.

**Pembaruan lokal 9 Oktober 2026:** satu file final `L-MING_B32_20261009_172056.csv` menambah total menjadi **87 file**: B32=19, B33=20, B34=22, B35=26. Validator **87/87 PASS**; **13.765 baris total = 13.153 baris sensor + 612 metadata historis**, dengan **10.881 purging** dan **2.272 collecting**. Total file light=31, medium=28, dark=28; artefak ekstraksi fitur kandidat 86 observasi **belum otomatis dihitung ulang**. Run tambahan bukan bukti spesimen baru independen.

## 4. Temuan prioritas awal (sebelum tindak lanjut Tahap 1)

1. **P0 — Integritas CSV.** Listener lama memasukkan event PHASE_CHANGE sebagai baris CSV kosong. Bug utama sudah diperbaiki dalam commit 54d3321. Audit lanjutan menambah validasi bilangan dan rentang ADC, deteksi indeks duplikat, perlindungan benturan nama file, serta regression test.
2. **P0 — Ketidakcocokan ekstraktor historis.** scripts/8_extract_features.py memakai MQ9 dan membutuhkan minimal 10 titik collecting; data aktif memakai MQ3 dengan sekitar 5 titik. Skrip historis kini menolak pencampuran skema dan tidak menimpa artefak lama. Ekstraktor kandidat MQ3 dibuat terpisah.
3. **P0 — Validitas evaluasi AI.** Random Forest B01–B05 sebelumnya menghasilkan akurasi uji 57,50% (baseline) dan 55,00% (tuned). Angka tersebut tidak berlaku untuk B32–B35. Cross-validation lama menggunakan StratifiedKFold pada run yang berkorelasi, sehingga skor CV lama belum dapat dijadikan bukti evaluasi bebas data leakage.
4. **P1 — Risiko salah atribusi fase.** adsCallback() membaca sensor sebelum processAcquisitionState() mengganti fase, tetapi mengirim JSON sesudahnya. Sampel tepat di batas fase mungkin diberi label fase yang baru. **Belum diubah**, karena perlu bukti timing melalui simulasi dan pengujian perangkat.
5. **P1 — Status AI perangkat.** Inferensi TinyML ATmega dinonaktifkan secara bawaan (USE_ON_DEVICE_INFERENCE=0); origin dan confidence tampil N/A. Jalur hasil inferensi dari Pi belum tervalidasi.
6. **P1 — Metadata dan protokol.** Event saat ini belum memiliki identitas akuisisi unik, identitas spesimen fisik, waktu kalender, sequence/acknowledgment, serta kontrak hasil dan error host yang terversi.
7. **P0 — Keselamatan diagnostik pin dan UART mendatang.** Perintah `#pin_scan;` mencakup D19/RX1 serta D20/SDA dan berpotensi mengganggu sambungan Pi atau bus sensor bila digunakan saat terhubung. Jangan menjalankan perintah ini sebelum ditinjau dan memiliki SOP.
8. **P0 — Label pada mode AI_TEST.** Event `ACQ_START` pada `ai_test` masih menyertakan pilihan roast/origin yang merupakan metadata default UI, bukan ground truth; listener saat ini tidak menyimpannya sebagai dataset labeled. Harus dipisahkan dalam kontrak inferensi mendatang.
9. **P0 — Keputusan label origin.** Pemetaan preset yang sama antarkolektor cocok pada kode yang beririsan, tetapi daftar preset tidak identik. Label TEM/MUK/CAW belum dibakukan berdasarkan definisi kopi nyata.

### Implementasi lanjutan Tahap 1 — 9 Oktober 2026

- **Pengamanan offline diterapkan:** `#pin_scan;` tidak lagi menjalankan pemindaian GPIO; `#valve_on/off/test;` dinonaktifkan secara bawaan (`ENABLE_MANUAL_ACTUATOR_TESTS=0`), dan hanya boleh diaktifkan untuk SOP bench. `#start;` serial membutuhkan seluruh ADC tersedia; `#scan;` I2C diblokir ketika akuisisi berlangsung.
- **Mode AI_TEST:** `ACQ_START` sekarang tidak mengeluarkan `sample_id`, `roast_level`, `origin_code`, `batch_id` atau `filename`. Untuk mode `labeled_data`, metadata tetap dikeluarkan agar listener lama kompatibel.
- **Urutan sampling:** `adsCallback` mengirim frame sensor ketika fase aktif **sebelum** mengubah fase dan mengirim `PHASE_CHANGE`/`ACQ_COMPLETE`. Frame idle/paused tidak diterbitkan sebagai sampel. Pada simulasi 1 Hz ideal jumlahnya 150 sampel (125 purging, 25 collecting), tetapi kondisi waktu dan kualitas sinyal fisik belum dibuktikan.
- **Regresi:** pemeriksaan kontrak firmware baru serta tes listener untuk AI_TEST tanpa label, COMPLETE ganda, dan STOP parsial ditambahkan. Detail: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`.

**Status Tahap 1: perbaikan offline telah diimplementasikan, verifikasi hardware belum dilakukan.** Narasi risiko sebelumnya adalah kondisi *sebelum perbaikan*, bukan indikasi bahwa perbaikan kode belum dikerjakan.

### Bukti tambahan bench pasif — 9 Oktober 2026

- Listener Windows (`pythonw.exe`, PID 16472) dilaporkan terhubung ke COM5 pada 115200 baud. Log mencatat START dan COMPLETE untuk `L-MING_B32_20261009_172056.csv`; validator layanan mengonfirmasi **150 baris sensor, nol parsial**.
- Pemeriksaan read-only terhadap CSV final mengonfirmasi lima siklus, **25 purging + 5 collecting** per siklus, interval `millis()` antar-sampel **996–1004 ms**, dan tidak ada ADC kosong/0/32767. SHA256 tercatat di `docs/reports/2026-10-09_TAHAP1_BENCH_PASIF_PRECHECK.md`.
- **Status yang benar:** satu akuisisi fisik-to-host **lulus pemeriksaan rekaman**; versi firmware dalam alat, gerak valve/pompa, pin/wiring, pemanasan gas, Nextion fisik, dan fault injection **belum diverifikasi**. Tidak ada akses serial tambahan atau operasi terhadap alat dari agen.
- SOP bench aktif baru berupa **draf untuk persetujuan operator**: `docs/SOP_BENCH_TAHAP1.md`. Alat QA pasif yang dapat dipakai ulang: `scripts/bench_stage1_passive_qa.py`.

### Hasil operator bench B37 (udara bersih) — 9 Oktober 2026

- Operator mengonfirmasi menggunakan Nextion pada batch B37 dengan selang ditempatkan pada **udara bersih**. Log listener: `L-MING_B37.csv` **150 sampel**, `M-MING_B37.csv` **152 sampel**; dua-duanya lengkap dan **PASS validator canonical**.
- Lima siklus terbaca pada kedua run. Target ketat 25 sampel purging + 5 collecting per siklus: `L-MING_B37.csv` **PASS**, `M-MING_B37.csv` **FAIL** karena collecting siklus 1 dan 5 berjumlah 6 sampel. `sample_idx` tetap kontigu. Ini tidak langsung membuktikan adanya masalah valve.
- **Keputusan data:** kedua file B37 diberi status **BENCH_ONLY / NOT ELIGIBLE FOR COFFEE TRAINING** melalui `data/analysis/bench_only_exclusions.csv` dan laporan `docs/reports/2026-10-09_TAHAP1_BENCH_B37_UDARA_BERSIH.md`. Label L-MING/M-MING berasal dari UI dan **tidak** mendeskripsikan medium udara bersih. CSV asli tidak diubah.
- Status Tingkat B yang terbukti: operator menjalankan sesi dari Nextion, serial host menerima sampai COMPLETE, dan file final valid secara struktur. Identitas firmware dan gerakan valve/pompa serta semua uji gagal belum dibuktikan.

**Addendum konfirmasi operator:** operator telah mengonfirmasi perpindahan pompa/valve mengikuti fase nominal 25/5 detik dan layar Nextion sampai halaman selesai tanpa error. Ini merupakan **observasi fungsi utama oleh operator**, bukan timestamp perpindahan valve yang direkam instrumen. Masalah collecting tambahan pada M-MING B37, versi firmware ter-flash, dan uji fail-safe masih terbuka.

### Tahap 2 — Audit dataset dan provenance

- `scripts/stage2_dataset_audit.py` menghasilkan enam artefak QC di `data/analysis/stage2/` berikut manifest SHA256 untuk seluruh **89 CSV B32+** pada mesin ini. **87 kandidat MQ3 B32–B35** valid secara struktur dan **dua B37 bench udara bersih dikecualikan**.
- Matriks 23 kode kopi × B32–B35 memiliki **9 sel kosong** dan **4 sel file berulang**. Terdapat **33 flag respons relatif file–kanal untuk review**, tanpa pembuangan data otomatis. Proxy perubahan purging dan baseline antarbatch masih tercampur faktor spesimen/hari/warm-up.
- P0 sebelum AI: label origin TEM/MUK/CAW dan `physical_specimen_id`, waktu kalender, urutan pengambilan serta identitas firmware belum dapat dibuktikan dari CSV. Status training kandidat **belum disetujui**.
- Skrip grafik `plot_sensor_pattern.py` diperkuat agar **tidak memasukkan bench B37 sebagai kopi** atau batch baru yang belum direview ke grafik per origin. Laporan: `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md`.

### Tahap 3 — Ekstraksi fitur terversi dan parity host

- Snapshot Tahap 2 **87 kandidat** diperiksa ulang pada tingkat siklus/indeks: **86** lolos kontrak fitur, sementara `L-CAW_B34.csv` ditahan karena hilang indeks purging **8** pada siklus 1. Raw tetap tidak diubah; validator umum Tahap 2 tidak menyatakan kesalahan ini.
- `data/processed/stage3_v1/` menyimpan kandidat **62 dan 82 fitur**, tujuh kelompok ablation tanpa seleksi berbasis label, feature quality deskriptif, manifest SHA256 dan daftar rejections. Unit observasi tetap **satu CSV berisi lima siklus**, bukan lima spesimen.
- `extract_sensor_features` digunakan pada kode akuisisi training serta simulasi sensor-only in-memory; tes parity **PASS**. Artefak 62-fitur lama 86 file dan artefak baru 86 file **berbeda cohort** (85 file sama; `L-CAW_B34.csv` diganti oleh `L-MING_B32_20261009_172056.csv`).
- **Belum ada model dilatih, benchmark akurasi, atau deployment Pi**. Pilihan fitur terbaik hanya dapat ditentukan setelah CV grup dalam Tahap 4–5 dan konfirmasi provenance label/spesimen.

## 5. Batas pemeriksaan dan keputusan

Yang dilakukan: kompilasi offline, pengujian parser/validator, pengecekan kontrak HMI, dan analisis berkas CSV yang tersedia. Tidak ada akses COM5, restart listener, penulisan EEPROM, kalibrasi, penggerakan pompa, flashing, training model, maupun deployment Raspberry Pi.

**Keputusan:** kesiapan perangkat lunak untuk pemrosesan CSV secara struktural cukup baik; klaim generalisasi AI maupun E2E perangkat fisik **belum terpenuhi**. Fitur baru berstatus kandidat penelitian, bukan model siap deployment. Inventaris Tahap 0 telah diperbarui dengan sumber acuan dan pemilik masing-masing masalah terbuka; Tahap 1/2/7/9 tetap memiliki pekerjaan yang wajib dibuktikan.

Dokumen lanjutan:

- **01_MASTER_E2E_ROADMAP.md** — peta jalan utama.
- **02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md** — baseline, koreksi pin, dan daftar keputusan terbuka.
- **03_AI_MODEL_RESEARCH_AND_EVALUATION.md** — penelitian dan metodologi AI.
- **04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md** — rancangan integrasi.
- **06_INDEPENDENT_AUDIT_QA_QC.md** — temuan audit serta bukti pengujian.
