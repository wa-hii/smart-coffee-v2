# Kondisi Aktual Smart Coffee E-Nose v2 — audit Tahap 0–1, 9 Oktober 2026

## 13 November 2026 — Audit ulang: FT232RL adalah IC ONBOARD PCB kedua

Operator memastikan **FT232RL berada di PCB custom ATmega2560**;
COM11 Windows `VID:PID 0403:6001`, serial `A10KNJBLA`
memvalidasi enumerasi FT232R-family, **bukan** keberadaan
bootloader/komunikasi ATmega. TIDAK perlu menambah adaptor
FT232RL eksternal. Tidak ada tombol RESET fisik, namun
auto-reset **mungkin** tersedia bila DTR# FT232RL pin 2
dirutekan lewat kapasitor ke RESET ATmega; net PCB belum
diverifikasi. Upaya `wiring`/115200 sebelumnya timeout.

Build RF30 (35.770 Flash, 3.917 global RAM) dan SHA256
kandidat cocok, HMI 12 halaman/23 event dan QA 900 sampel
PASS offline. **Origin/confidence RF500 masih N/A by design**.
`platformio.ini` lokal masih `upload_port=COM4`, tidak
diubah. Receiver otomatis Windows dihentikan dan COM11
sekarang bebas; file status receiver lama bukan status live.
**Pi di Tailscale saat audit tercatat OFFLINE**, ping
`100.103.211.125` dan SSH timeout. Flash/EEPROM/Nextion
fisik PCB kedua masih belum terverifikasi. Laporan:
`docs/reports/2026-11-13_FULL_AUDIT_SECOND_PCB_ONBOARD_FT232RL_COM11.md`.

## 13 November 2026 — FT232R PCB kedua di Windows COM11, bootloader timeout

Operator memindah FT232R dari Pi ke laptop Windows.
`python -m serial.tools.list_ports -v` mengidentifikasi
`COM11`, `0403:6001`, serial `A10KNJBLA` (FTDI; selaras
dengan adaptor `A10KNJBL` yang sebelumnya di Pi).
Receiver auto `pythonw.exe` PID 15160 sempat memiliki
COM11; setelah memastikan tidak ada file `.incoming`,
receiver dihentikan dan dibiarkan berhenti untuk pengujian
programmer.

Satu percobaan read-only `avrdude 6.3 -p m2560
-c wiring -P COM11 -b 115200 -n -v` menghasilkan
`stk500v2_ReceiveMessage(): timeout`; signature
ATmega2560 tidak terbaca, tidak dilakukan upload.
Backup Flash/EEPROM PCB kedua tidak ditemukan dalam
inventaris privat saat ini. Firmware RF30 dan model
Pi masih staged; **NO-GO physical deployment**.
Laporan:
`docs/reports/2026-11-13_COM11_WINDOWS_FT232R_BOOTLOADER_TIMEOUT.md`.

## 12 November 2026 sore — Preflight deployment PCB kedua fail-closed

USB FT232R Pi `A10KNJBL` tetap aktif dan model RF500
serta firmware RF30 kandidat valid. Skrip baru
`scripts/pi_rf30_second_pcb_release_gate.py` dibuat,
lulus tes offline, disalin dan dieksekusi pada Pi secara
read-only. Status **`NO_GO_PHYSICAL_DEPLOYMENT`**:
backup Flash/EEPROM asli PCB kedua belum dapat diverifikasi,
dan programmer belum membaca signature MCU pada sesi ini.
Tidak ada upload/EEPROM write/bridge live. Firmware
terpasang di PCB kedua tetap tidak diketahui.
Detail: `docs/reports/2026-11-12_SECOND_PCB_RELEASE_GATE_FINAL.md`.

## 12 November 2026 pukul 17:15 — Upload RF30 PCB kedua tidak dapat diteruskan

Operator mengizinkan upload ke PCB kedua dan menyatakan prasyarat
fisik telah dipenuhi. Pemeriksaan SSH/FT232R dan SHA256 model
RF500/firmware RF30 di Pi PASS, tetapi **satu pemeriksaan ulang
signature** `avrdude -p m2560 -c wiring -b 115200 -n`
tetap gagal dengan `stk500v2_recv() timeout` (batas 15 detik,
exit 124). Bootloader tidak memberikan signature, maka **tidak
ada penulisan Flash/EEPROM atau aktivasi bridge RF500**.

`lsusb` hanya mendeteksi FT232R, tidak ada USB ISP programmer
lain; backup/EEPROM PCB kedua tidak ditemukan pada lokasi
Pi yang diperiksa. Pi dan USB tetap terhubung setelah uji.
Status **NO-GO fisik** sampai programmer/bootloader benar-benar
berkomunikasi dan backup/rollback khusus PCB ini terverifikasi.
Laporan: `docs/reports/2026-11-12_SECOND_PCB_RF30_UPLOAD_ATTEMPT_BOOTLOADER_UNRESPONSIVE.md`.

## 12 November 2026 — PCB kedua: AVRDUDE bootloader timeout, belum boleh flash

SSH/Tailscale ke Pi 5 aktif dan FT232R `A10KNJBL` terdeteksi.
`avrdude` 7.1 arm64 disiapkan di staging Pi dengan dependensi
terisolasi tanpa sudo atau instalasi sistem. Satu percobaan
read-only `-p m2560 -c wiring -b 115200 -n -v` via
FT232R berakhir dengan `stk500v2_recv() timeout`, dihentikan
setelah 20 detik (exit 124). **Tidak ada signature MCU
atau backup Flash/EEPROM PCB kedua.** Tidak ada upload.

Pi tetap terhubung pascapercobaan, tidak ada error xHCI atau
disconnect baru yang teramati; ada disconnect/reconnect
FT232R pada 17:01 sebelum uji. RF500 dan firmware kandidat
RF30 bootguard tetap terverifikasi di staging Pi, namun
`HOST_STAGED_NOT_MCU_VERIFIED` dan live masih dinonaktifkan.
**NO-GO** untuk flashing sampai jalur reset/bootloader/ISP
terverifikasi dan backup spesifik PCB kedua tersedia. Rincian:
`docs/reports/2026-11-12_SECOND_PCB_AVRDUDE_SIGNATURE_TIMEOUT_NO_FLASH.md`.

## 12 November 2026 — PCB kedua berhasil serial-open tetapi 0 byte; RF30 bootguard staged

Dengan persetujuan operator, G2 passive probe FT232R Pi
`A10KNJBL` dibuka **sekali selama 8 detik** (115200 baud)
dan ditutup kembali; `SERIAL_DATA_INCONCLUSIVE`, **0 byte RX,
0 perintah dikirim**, tanpa disconnect atau xHCI dead baru
di journal kernel. Ini belum mengidentifikasi firmware PCB
kedua maupun penyebab Nextion tetap `Initializing Systems`.

Kandidat RF30 khusus PCB kedua diperkuat timeout I²C 25ms
dan melewati scan seluruh alamat I²C saat boot, tanpa
mengubah default, SVM30, HMI atau kontrak inferensi.
Firmware RF30 kompilasi PASS (**35.770 B Flash**, **3.917 B
SRAM global**), pengujian regresi offline PASS. Image
privat SHA256 `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`
disalin ke Pi staging dan checksum cocok.

**ATmega PCB kedua belum di-flash**, firmware aslinya
belum diketahui, backup Flash+EEPROM belum ada dan
jalur bootloader belum diverifikasi. Backup SVM30 milik
PCB lama **bukan rollback PCB kedua**. Uji RF500 E2E
tetap BLOCKED sampai verifikasi onsite, backup khusus
alat ini, dan izin upload spesifik. Laporan:
`docs/reports/2026-11-12_SECOND_PCB_G2_RX_ZERO_BOOTGUARD_RF30_STAGED.md`.

## 12 November 2026 — Koreksi PCB target: alat kedua, Nextion masih initializing

Operator mengonfirmasi FT232R `A10KNJBL` terhubung dari Pi via
USB ke **PCB ATmega2560 yang berbeda** dari perangkat SVM30
Windows COM5 pada 11 November. Nextion PCB kedua menunjukkan
`Initializing Systems` dan alat dilaporkan IDLE. Dengan demikian,
firmware terpasang dan backup Flash/EEPROM **PCB kedua belum
diketahui**; **jangan gunakan backup COM5/SVM30 alat lama sebagai
rollback** atau klaim image SVM30 sudah berada di PCB kedua.

SSH Pi, FT232R `/dev/ttyUSB0`, dan status Pi `throttled=0x0`
PASS pasif, tanpa pemilik port terdeteksi; tidak dilakukan
serial-open karena kemungkinan DTR/reset dan riwayat xHCI.
Pada source repo, MCU seharusnya mengirim `pHome` sekitar
3 detik setelah startup bila scheduler berjalan. Firmware
fisik belum diidentifikasi, sehingga kemungkinan inisialisasi
I²C terhambat, masalah UART2/HMI, atau masalah firmware/daya
belum dapat dibedakan. **RF500 live dan flash ditahan** sampai
jalur perangkat aman, backup khusus PCB kedua tersedia dan
persetujuan spesifik diberikan. Laporan:
`docs/reports/2026-11-12_SECOND_PCB_NEXTION_INITIALIZING_REMOTE_PREFLIGHT.md`.

## 12 November 2026 — Pi 5 kembali online dan RF500 replay PASS setelah boot ulang

Pi berhasil diakses kembali via Tailscale/SSH setelah gangguan
sekitar 15:42 WIB. Boot baru teridentifikasi pada 15:45 WIB
berdasarkan uptime; kernel monotonic merekam USB FT232R
`A10KNJBL` terpasang sekitar 3,96 detik setelah boot.
Tujuh pemeriksaan pasif selama sekitar 90 detik konsisten:
`/dev/ttyUSB0` tersedia, `throttled=0x0`, tidak ditemukan
USB disconnect pada log boot saat dicek. Penyebab reboot
sebelumnya belum teridentifikasi; stabilitas serial-open dan
900-sampel belum diuji.

Readiness RF500 di Pi tidak memiliki blocker host; hash model
valid dan replay 900 data dengan model asli serta ACK simulasi
PASS. Windows saat pemeriksaan tidak memiliki port COM,
sedangkan FTDI Pi berbeda dari COM5 yang sebelumnya dipakai
flashing. **Firmware RF30 belum di-flash ke ATmega.**
Menunggu verifikasi fisik, jalur programmer, SOP dan izin
spesifik upload. Laporan:
`docs/reports/2026-11-12_PI5_POST_REBOOT_RF500_READINESS.md`.

**Peringatan 12 November 2026 ±15:42 WIB:** Pi `enose-pi5`
tidak lagi terjangkau melalui SSH/Tailscale (timeout,
ping tanpa balasan, Tailscale offline). Pemeriksaan FT232R
pasif 15:22–15:38 tetap tercatat, **tetapi status USB
terbaru tidak diketahui**. Pemeriksaan tahap 1 menjadi
**PARTIAL/BLOCKED** untuk kesiapan live dan firmware RF30
**TIDAK di-flash**. Lihat addendum laporan FT232R di bawah.

## 12 November 2026 — FT232R Pi pasif stabil, firmware RF30 belum di-flash

SSH Pi terhubung; FT232R Pi `A10KNJBL` terpasang sebagai
`/dev/ttyUSB0` sejak 15:22:01 WIB. Lima pemeriksaan pasif
selama sekitar 61 detik mempertahankan by-id yang sama dengan
`get_throttled=0x0`; log boot hingga 15:38:45 WIB tidak
menunjukkan USB disconnect. **Ini bukan bukti kestabilan
serial-open atau akuisisi 900 sampel.** Tidak ada port yang dibuka.

Build RF30 return dan delapan QA offline PASS, checksum image
RF30/rollback SVM30 cocok. Firmware **SVM30 standalone tetap
terpasang sebagaimana terakhir diverifikasi**; status fisik
terkini belum dibaca. Perlu konfirmasi bahwa FTDI Pi
`A10KNJBL` dan FTDI Windows COM5 `A10KMM3SA` menuju MCU
yang dimaksud, SOP daya/rollback dan izin flashing eksplisit
sebelum pindah ke Pi RF500. Laporan:
`docs/reports/2026-11-12_RF30_PI_FT232R_PASSIVE_STABILITY_CHECK.md`.

## 12 November 2026 — SVM30 dibekukan pada branch baru; RF500 Pi disiapkan

Branch `backup/atmega-svm30-standalone-20261112`
berhasil dibuat dan dipush pada commit
`7db96db006f780a9e78dcbea3830b21a170ae6cd`.
Branch `wahyu` tetap aktif dengan perubahan
lokal pengguna aman. Artefak model dan image
privat tetap diabaikan Git.

SSH Pi 5 `enose-v3@enose-pi5` berhasil;
RF500 `final_model.joblib` SHA256
`b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d`
valid di staging, dan replay 900 sampel
→ prediksi RF → paket protokol/ACK mock
lulus **di Pi**. Pyserial 3.5 terpasang
pada venv staging saja. FT232R Pi
`A10KNJBL` sempat tidak terdeteksi,
kemudian muncul kembali pada
`/dev/ttyUSB0`; port belum dibuka dan
stabilitas saat serial-open belum diuji.

Kandidat pasangan MCU `rf30_return_bench`
berhasil kompilasi (35.748 byte Flash,
3.917 byte SRAM global), SHA256 HEX
`13b764d4f8b4aad3c09413bdc7a18094c1e90bf18be83dec5b6b2cb103e92440`.
Disimpan privat di
`private/rf30_pi_restore_image/20261112/`.
**ATmega masih menjalankan SVM30 standalone
yang terakhir di-flash pada B6**, belum
diubah/di-reset/diakses serial selama pekerjaan
ini. Pi RF belum menghasilkan pResult fisik.
Rincian:
`docs/reports/2026-11-12_RESTORE_PI5_RF500_STAGING.md`.

## 11 November 2026 — Uji L-TOR kedua benar LIGHT, origin dan confidence tetap N/A

Operator melaporkan hasil uji fisik kedua untuk kopi
L-TOR dari sampel/kemasan sama: **LIGHT** (benar),
setelah uji pertama **DARK** (salah). Jadi fungsi
klasifikasi MCU→Nextion terbukti berjalan, namun
hasil dua pengulangan untuk sampel yang sama tidak
konsisten. Dua pengamatan tidak membuktikan akurasi
atau repeatability statistik.

Tampilan Coffee Origin dan Roast Probability/
Confidence tetap **N/A** sesuai source firmware
standalone: `tOrigin/tRConf/tOConf=N/A`, progress
bar probabilitas 0. Belum ada model origin atau
probabilitas roast terkalibrasi. Tidak ada
modifikasi firmware, EEPROM, COM5, atau file Nextion.
Rincian pada
`docs/reports/2026-11-11_B6_LIGHT_TO_DARK_CLASSIFICATION_INCIDENT.md`.

## 11 November 2026 — B6 fisik menghasilkan DARK padahal LIGHT

Operator mengonfirmasi AI Test pada LCD Nextion
telah selesai dan menampilkan DARK untuk kopi
yang sebenarnya **L-TOR (Light Toraja)**. Ini membuktikan hasil
klasifikasi MCU tampil di LCD tetapi **prediksi
fisik pertama salah**.

Analisis replay lokal atas 199 sampel berlabel
menemukan 156/199 prediksi sesuai label dan
2/59 LIGHT→DARK; 199/199 prediksi native C++
tetap setara dengan Python. Karena standalone
tidak menyimpan 900 data ADC atau 30 fitur dari
run fisik, akar masalah belum terbukti.
Tidak ada perubahan firmware/COM5/EEPROM/TFT.
Laporan:
docs/reports/2026-11-11_B6_LIGHT_TO_DARK_CLASSIFICATION_INCIDENT.md.

Replay **khusus TOR** memiliki 34 sesi: dari
14 sesi L-TOR, **13 terprediksi LIGHT, 1 MEDIUM,
0 DARK**. Dengan demikian kasus fisik L-TOR→DARK
tidak muncul dalam replay TOR yang tersedia.
Penyebabnya tetap belum dapat ditentukan tanpa
fitur/ADC fisik yang tersimpan.

## 11 November 2026 — B6 standalone AI Test siap, menunggu START dari Nextion fisik

Pengguna mengonfirmasi sesudah flashing SVM30
bahwa `pHome`, pompa/dinamo, dan valve pada IDLE
normal. Port COM5 FT232R masih terdeteksi,
receiver tidak digunakan, checksum dan manifest
upload ATmega2560 menunjukkan **50006 bytes
ditulis+diverifikasi**. Profil standalone
menonaktifkan remote `#start` dari Serial0
dan tidak membutuhkan Raspberry Pi/CSV.

**Tidak ada bukti START AI TEST fisik sudah
ditekan atau sesi 30 siklus selesai.**
Prosedur final disusun di
`docs/reports/2026-11-11_B6_AI_TEST_OPERATOR_PROCEDURE.md`.
Langkah pengguna sekarang:
`pHome → AI Test → START AI TEST`, observasi
30×(25s purge + 5s collect) lalu
`pResult.tRoast`. Tidak melakukan
reset COM5/flash ulang/aktuator remotely.

## 11 November 2026 — B6 firmware SVM30 standalone FLASH + VERIFY PASS

Dengan izin eksplisit operator untuk flashing,
firmware standalone SVM30 **benar-benar terpasang**
ke ATmega2560 melalui **COM5** FT232R `A10KMM3SA`.
Satu kali `avrdude` `-p m2560 -c wiring -P COM5
-b 115200 -D` menulis **50.006 byte Flash**
dan **memverifikasi 50.006 byte (PASS)**,
exit code 0 dalam **24,27 detik**. Tidak ada
perintah menulis EEPROM, fuse, area bootloader
atau file Nextion. Bootloader area aman secara
alamat payload; checksum image di
`private/svm30_standalone_firmware.hex`
tetap `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`.

Backup Flash/EEPROM awal tetap di
`private/b6_com5_readback/20261111_170948/`;
rollback application-only telah dibuat dan
tervalidasi offline (belum diuji fisik).
Upload log dan manifest disimpan privat di
`private/b6_com5_svm30_deployment/`.
**B6 belum PASS end-to-end**: status boot
`pHome` setelah flash, sensor dan tombol AI
Test 900-sampel/30-siklus, serta hasil
`pResult` belum dikonfirmasi operator.
Tindakan berikutnya adalah pemeriksaan
visual startup, bukan pembukaan ulang COM5.
Rincian `docs/reports/2026-11-11_B6_COM5_SVM30_FLASH_VERIFIED.md`.

## 11 November 2026 — B6 pHome normal sesudah backup, izin flashing pending

Operator mengonfirmasi bahwa **setelah backup COM5**
Nextion tetap di `pHome`, pompa/dinamo tetap hidup
sesuai IDLE, dan solenoid valve diam. Pemeriksaan
pasif terbaru dengan backup Intel HEX yang telah
diverifikasi menyisakan **dua blockers**:
`PROGRAMMER_POWER_SOP_NOT_VERIFIED` dan
`SPECIFIC_UPLOAD_APPROVAL_MISSING`. COM5 masih
terdeteksi, receiver lama tetap berhenti, model/
firmware kandidat dan backup tidak berubah.
**Tidak ada flashing/pengujian AI fisik baru**.
Lihat addendum laporan
`docs/reports/2026-11-11_B6_COM5_FLASH_EEPROM_READBACK.md`.

## 11 November 2026 17:09–17:11 WIB — B6 backup Flash/EEPROM COM5 PASS (bersyarat)

Dengan izin pengguna, receiver COM5 `lcd_acquisition_service.py`
PID **14628** dihentikan secara spesifik memakai
`Stop-Process -Force` karena `pythonw.exe` tidak
memiliki jendela untuk `CloseMainWindow()`.
Sebelum penghentian, tidak ada file .incoming aktif;
autostart dan CSV tidak diubah. Receiver tidak restart.

`avrdude -c wiring -p m2560 -P COM5 -b 115200 -n`
berhasil melakukan **satu sesi backup read-only**,
signature chip **0x1e9801**, Flash dan EEPROM exit 0,
durasi 73,61 detik. Bukti privat di
`private/b6_com5_readback/20261111_170948/`.
EEPROM mencakup 4096/4096 byte. Flash Intel HEX
mencakup prefix 261406/262144 byte, tanpa internal
gap, tetapi **738 byte terakhir tidak tercantum**;
ini konsisten dengan suffix `0xFF` yang dipangkas
namun **belum dibuktikan terbaca**. File asli dan
checksum dipertahankan, tidak di-Git.

**Belum ada flash firmware SVM30, EEPROM write atau
tes AI fisik**. Setelah kemungkinan reset bootloader
melalui DTR, tampilan Nextion `pHome` belum
dikonfirmasi kembali oleh operator. Preflight
tetap NO-GO untuk upload sampai SOP daya/recovery
dan izin flashing spesifik terpenuhi.
Laporan `docs/reports/2026-11-11_B6_COM5_FLASH_EEPROM_READBACK.md`.

## 11 November 2026 — Nextion pHome sudah dikonfirmasi operator, B6 belum GO

Pengguna menyatakan layar Nextion **sudah tampil pHome**
setelah PCB terhubung COM5. Ini menyelesaikan
**konfirmasi startup secara visual oleh operator**
yang sebelumnya outstanding, tetapi bukan validasi
UART/firmware versi terpasang atau boot jangka panjang.

Preflight pasif `--operator-reported-phome` kini
menyisakan **4 blockers**: receiver PID 14628 masih
connected di COM5, backup firmware/EEPROM belum ada,
jalur pemrograman dan SOP daya belum diverifikasi,
serta tidak ada izin khusus upload. Tidak ada
serial open, DTR reset, penghentian receiver, atau
flashing. Detail pada addendum
`docs/reports/2026-11-11_B6_COM5_WINDOWS_PREFLIGHT.md`.

## 11 November 2026 — B6 COM5 Windows preflight NO-GO

Pengguna memindahkan koneksi ATmega ke COM5 laptop Windows.
PnP mendeteksi adaptor FTDI `0403:6001`, serial
`A10KMM3SA`, berbeda dari FT232R `A10KNJBL`
yang ada di Pi sebelumnya. Namun, proses penerima
`pythonw.exe` PID 14628 `lcd_acquisition_service.py
--port auto --baud 115200` masih **connected ke COM5**
menurut status/log pukul 15:16 WIB. Proses tidak dihentikan.

Firmware standalone privat dan SHA-256 model **valid**,
tetapi belum ada backup Flash/EEPROM, verifikasi koneksi
programmer serta Nextion `pHome` baru, atau persetujuan
SOP upload spesifik. `scripts/svm30_b6_preflight.py`
melaporkan **NO_GO** tanpa membuka COM5.
**Tidak ada flashing, restart, DTR, pembacaan serial,
operasi pompa/valve atau modifikasi HMI.**
Lihat `docs/reports/2026-11-11_B6_COM5_WINDOWS_PREFLIGHT.md`.

## 11 November 2026 — SVM30 standalone B4 compile PASS, B6 hardware BLOCKED

Profil standalone yang **tidak membutuhkan Raspberry Pi atau CSV**
sekarang mengintegrasikan 30 siklus sensor, fitur streaming,
SVM RBF final 125 SV di Flash, dan kelas Light/Medium/Dark
pada halaman Nextion `pResult`. Semua perubahan bersifat
**compile-time opt-in**; build default dan pengaturan
COM lokal tidak diubah. Host streaming data/Take Data/
Result Save dinonaktifkan pada profil standalone,
dan hasil tidak valid tetap `N/A`.

Build standalone penuh `svm30_standalone` PASS:
**50.006B Flash / 4.189B global SRAM**; compiler
stack diagnostic frame `Classifier::predict` 663B
(bukan stack peak). Header model privat dan image HEX
berada di `private/`, bukan GitHub. B5 pengukuran
stack puncak serta latensi klasifikasi 16MHz belum selesai.

**B6 belum dilakukan**: pemeriksaan SSH read-only di
Pi pukul 15:41 WIB masih tidak menemukan FT232R atau
`/dev/ttyUSB0`; Nextion fisik terakhir dilaporkan
tertahan pada `Initializing Systems`. Tidak ada
flashing/reset/operasi aktuator. Laporan:
`docs/reports/2026-11-11_B4_B6_SVM30_STANDALONE_INTEGRATION_QA.md`.

## 11 November 2026 — Backup embedded AI B1–B3 PASS (offline)

Karena USB Raspberry Pi–PCB xHCI bermasalah, disiapkan
alternatif inferensi tanpa Raspberry Pi memakai model asli
**SVM RBF 30 fitur / 125 support vector** (`final_svm.joblib`).
Modul C++ ekstraksi streaming `src/embedded_svm30_features.cpp`
dan klasifikasi libsvm RBF `src/embedded_svm30_classifier.cpp`
berhasil diimplementasi, **belum diaktifkan pada firmware utama**.

Referensi sklearn **1.7.2** dan helper pengguna dibandingkan
terhadap native C++ pada **199 rekaman valid: 0 perbedaan
prediksi kelas**, max error fitur **0,0229167 ADC** dan
max error skor pasangan kelas **3,6055e-6**. Sepuluh
kasus sesi rusak ditolak. Build AVR uji terisolasi PASS
**22.356 byte Flash, 431 byte SRAM global**, parameter model
di PROGMEM (header privat diabaikan Git).
Build utama `mega2560` tetap 34.760B Flash/3.899B RAM,
tanpa perubahan perilaku. **B4 integrasi Nextion, B5
uji stack/latensi, B6 flash/validasi fisik belum dilakukan**;
perangkat dengan layar `Initializing Systems` tetap
hardware NO-GO. Laporan:
`docs/reports/2026-11-11_B1_B3_EMBEDDED_SVM30_QA.md`.

## 11 November 2026 12:28 WIB — Nextion stuck in Initializing Systems

Operator melaporkan PCB dan LCD masih menyala setelah G2 gagal,
tetapi Nextion tertahan pada splash `Initializing Systems`.
Source `src/main.cpp` terakhir semestinya mengirim `page pHome`
melalui Serial2 9600 baud setelah sekitar 3 detik di
`serialCallback()`; scheduler baru aktif **sesudah** setup
sensor dan scan I²C selesai. Ini hipotesis masalah startup
MCU / UART Nextion / I²C / supply, **bukan bukti diagnosis
spesifik**, karena firmware fisik belum dapat diidentifikasi.
Pi read-only check 12:28 menunjukkan FT232R tetap hilang dan
`/dev/ttyUSB0` belum pulih. Hardware G2/G3 tetap NO-GO,
tidak ada percobaan reset/serial ulang. Lihat addendum
`docs/reports/2026-11-11_G2_USB_XHCI_FAILURE_1200.md`.

## 11 November 2026 pukul 11:59–12:00 WIB — G2 FAILED, xHCI host died

Operator mengizinkan G2 dan menyatakan alat IDLE serta berada di dekat
PCB. Setelah precheck by-id FT232R `A10KNJBL`, satu pembacaan serial
pasif 12 detik dicoba melalui Pi. **serial.open() gagal dengan
`Errno 19: No such device` sebelum ada data UART dibaca**.
Kernel 11:59:29 WIB mencatat `xHCI host controller not responding`,
`HC died; cleaning up`, lalu FT232R disconnect. Pada 12:00:48
SSH Pi masih berjalan dan throttled=0x0, tetapi `/dev/ttyUSB0`
dan FT232R tidak tersedia lagi. Tidak ada TX serial, START,
flashing, atau operasi aktuator yang diperintahkan program.
**G2/G3 HARDWARE NO-GO**, tidak diulang atau di-reset remote.
Laporan: `docs/reports/2026-11-11_G2_USB_XHCI_FAILURE_1200.md`.

## 11 November 2026 — G2 precheck NO-GO dan file final SVM pengguna

Pengguna mengunggah enam file SVM (termasuk `final_svm.joblib`,
`final_svm_info.json`, dan helper). Metadata final menunjukkan
**SVM RBF 30 fitur, C=1, gamma=0.1, 176 sesi**; berbeda dari kandidat
SVM **9 fitur** yang sebelumnya disiapkan di Pi. Kedua pipeline
**tidak bisa dipertukarkan** dan file baru belum di-deserialize/di-deploy.

Precheck SSH/sysfs G2 atas Pi 5 pukul 11.46 WIB menunjukkan FT232R
`A10KNJBL` masih terdeteksi sebagai `/dev/ttyUSB0`, port tanpa
pemilik, ModemManager/getty inactive, throttled=0x0. Akan tetapi,
kernel melaporkan **hub USB disabled (EMI?) dan disconnect/reconnect
pukul 10.35 WIB**. Probe G2 lama masih mengunci serial FT232 berbeda
`A10KMM3S`, dan konfirmasi operator **onsite** belum ada.
**Tidak ada port serial yang dibuka, G2 live NOT RUN / NO-GO.**
Kondisi IDLE yang diberikan pengguna dicatat, tetapi tidak
dianggap bukti bahwa masalah USB/kelistrikan sudah beres.
Lihat `docs/reports/2026-11-11_G2_PRECHECK_AND_USER_FINAL_SVM.md`.

## 11 November 2026 — model aktif kandidat SVM RBF 9 fitur

Atas arahan pengguna, penelitian beralih dari kandidat RF500 menuju
**SVM RBF** sembilan fitur dari TGS822, TGS2602 dan TGS816. Model
SVM asli (bukan simulasi) telah di-fit di Raspberry Pi 5 dengan
scikit-learn 1.7.2 pada 133 rekaman a+b; holdout c 66.
Skor seimbang CV origin 0,5469, holdout c 0,6527.
Pipeline `StandardScaler + SVC` memakai baseline correction
per siklus, lalu fit Z-score hanya pada data training.

Artefak hanya di Pi staging, metadata di results repo; model
belum dipromosikan. Pengujian offline pada 900 sampel uji
berhasil menghasilkan `dark` dan payload `#rf30:<token>:dark;`
dengan ACK simulasi. Tidak ada serial USB dibuka, flashing
atau model output ke layar Nextion fisik. Alat tetap perlu
G0/G2/G3 onsite sebelum pemasangan aktif; FT232 serial saat
ini `A10KNJBL`. Laporan di `docs/reports/2026-11-11_SVM30_PI_TRAINING_AND_NEXTION_CANDIDATE.md`.

## 11 November 2026 — RF500 dijalankan di Pi; return protocol source-only

SSH Tailscale ke Pi 5 berhasil. FT232R sekarang serial `A10KNJBL`,
berbeda dengan alat uji Oktober, dan kernel mencatat USB disconnect
02:29 WIB lalu reconnect 02:31 WIB. USB serial **tidak dibuka** dan
firmware fisik **tidak di-flash**.

Model joblib RF500 asli diterima di folder Pi staging yang terisolasi;
SHA256 cocok dengan manifest dan scikit-learn 1.7.2 tersedia pada venv
terpisah. Pengujian offline CSV `D-CAT_B70.csv` 900 baris memberi
`dark` (RF vote 1.0 belum terkalibrasi). Replay 900 ADC dari file
tersebut lewat parser Pi/model asli membentuk paket kandidat
`#rf30:B1F503A9:dark;`, ACK disimulasikan saja.

Firmware source kini punya parser token sesi, timeout 30 s dan
pengembalian kelas pada `pResult`, namun **release gate default OFF**
(`ENABLE_PI_RF30_RETURN=0`). Build standar/bench dan QA simulasi
lulus; USB Pi→MCU live, MCU flash dan Nextion fisik tetap NOT RUN,
menunggu identitas perangkat/USB stabil/SOP G0/G2/G3.
Laporan: `docs/reports/2026-11-11_RF30_PI_REMOTE_STAGING_AND_RETURN_PROTOCOL.md`.

## 10 November 2026 — penyamaan source AI Test dan Take Data: 30 siklus

**Source firmware telah disinkronkan (belum di-flash pada PCB):** tombol
Nextion `EVT:AI_START` dan Take Data memicu 30 siklus, tiap siklus
purging 25 detik + collecting 5 detik, total 900 sensor samples pada
sampling nominal 1 Hz selama 900 detik (15 menit). Kontrak
`FW_HELLO` sekarang mengiklankan `data_cycles_total=30` dan
`ai_cycles_total=30`. UI `pTestRun` menghitung progres/ETA untuk
durasi 900 detik; tulisan firmware berubah menjadi `DATA30-AI30`
tanpa mengedit HMI pengguna.

Adapter Pi aktif mengenali 30 siklus dan memberi batas pendengar 1.260
detik termasuk waktu operator menekan tombol. Data lima siklus historis
G3 tetap dapat diuji hanya dalam mode legacy khusus, tetapi **bukan**
input untuk RF500 30-siklus. Program Raspberry Pi kandidat baru dapat
menghasilkan prediksi di host setelah validasi 900 titik; jalur hasil
Pi → MCU → Nextion belum di-deploy dan pResult masih **N/A**.
Tidak ada serial fisik, flashing atau pompa yang dijalankan.
Laporan: `docs/reports/2026-11-10_TAKE_DATA_AI_TEST_30CYCLE_SYNC.md`.

## 19 Oktober — receiver v9 salvage sampai ACQ_COMPLETE (software-only)

Kasus operator ALAT_3 COM7 `L-CAT_B63`: pada baris 128, frame sepanjang
257 byte gagal `invalid_json_or_encoding`, dengan `json_error_pos=256`,
`Invalid control character at`, `ends_with_brace=False`; error serupa
terjadi dua kali. Ini bukan duplicate dataset. Parser PC mendukung
reassembly data serial dalam chunk 256 byte, dibuktikan oleh QA.
Root cause frame terpotong belum dibuktikan.

Mode opt-in `--salvage-on-frame-error` memperlakukan satu frame rusak atau
sample index duplikat sebagai *recoverable*, sehingga memantau semua 30
siklus hingga `ACQ_COMPLETE`. Tidak menambah sampel buatan.
Sesi 900 valid + validator PASS dipublikasikan di `data/raw/devices`.
Jika sensor valid kurang dari 900, hasilnya di `incomplete` bersama
`.quality.json`; ini bukan dataset training yang lengkap. Gangguan
USB fisik/timeout panjang tetap fatal dan memerlukan pemeriksaan nyata.

Uji offline mencakup 899 valid + 1 corrupt + duplicate yang tetap
mencapai `ACQ_COMPLETE` dan disimpan sebagai incomplete, lalu sesi
berikutnya dengan 900 valid + duplicate yang dipublikasikan PASS.

## 19 Oktober — ALAT_2 L-MING_B60 ditolak sebagai malformed JSON

Log Windows Probook receiver v7:
`enose-acquisition.ALAT_2 | ERROR | SERIAL FRAME REJECTED
reason=malformed_json detail=invalid_json_or_encoding frame_bytes=272
active_session=True accepted_rows=351`. File tetap berada di
`data/raw/devices/ALAT_2/incomplete`. Bukan masalah frame >4096 byte;
parser mengalami error JSON atau UTF-8 yang pada v7 sama-sama dipetakan
ke `invalid_json_or_encoding`. Audit firmware menunjukkan sensor JSON
dikirim `Serial.print()` + newline dan pembacaan SHT30 ber-CRC, tetapi
tidak membuktikan byte selalu utuh pada USB.

Receiver v8 software-only menambahkan `fault_class`, JSON parser
error position/message, status penutup `}`, dan byte offset UTF-8 invalid
tanpa merekam isi frame. Offline QA PASS. Root cause belum dikonfirmasi;
observasi parser dan tes kabel/hub/daya fisik harus dilakukan prospektif,
ketika alat sudah IDLE. Jangan meloloskan incomplete CSV.

## 19 Oktober — serial frame reject pada 3 alat (laptop Probook)

Log operator menunjukkan `L-TOR_B61` pada ALAT_1 masuk incomplete
setelah 758 baris dan `L-CAT_B63` ALAT_3 setelah 487 baris; alasan umum
`serial frame corrupt or oversized`. Audit `serial_wire.py`: batas
JSON = 4096 byte/baris, chunk USB 256 byte dirangkai kembali, sehingga
batas chunk tidak menyebabkan frame gagal. `decode_line` menolak malformed
JSON, encoding invalid, NUL, duplicate keys, nonfinite number; framer
menolak oversized lines yang dapat muncul jika delimiter newline hilang.
Paket v7 mencatat reason/detail/ukuran frame tanpa merekam konten rusak;
tetap fail-closed dan menyimpan partial di incomplete. QA offline PASS.
Belum ada byte/log rinci dari Probook untuk membedakan malformed vs
oversized dan belum ada uji tiga alat fisik setelah perubahan.

## 19 Oktober — tindak lanjut laporan data kedua hilang pada 3 alat

Laporan operator laptop Probook: COM5 FTDI `A10KMM3SA`, COM6 FTDI
`A10KN6X9A`, COM7 FTDI `A10KMZQJA`. Receiver v5 ketiganya CONNECTED.
ALAT_1/COM5 `M-GRB_B61` dan ALAT_2/COM6 `L-MING_B51` sukses 900 baris
dan QA PASS. ALAT_3/COM7 `L-MING_B52` terputus USB saat 597 baris,
dipindahkan ke folder incomplete; Windows serial error `ClearCommError
Access is denied`, kemudian `usb_not_found`. ALAT_1/COM5 kemudian
mulai `M-GRB_B62`, tetapi potongan log belum menunjukkan completion.

Receiver v6 software-only menyediakan diagnostik status/log/CSV tiga
perangkat tanpa membuka COM, identitas alat pada pesan console, dan
alasan untuk completion tanpa sesi aktif. Uji offline **dua sesi berurutan
per alat, tiga alat paralel** memastikan receiver tidak berhenti setelah
sesi pertama pada data sintetis; tidak membuktikan USB fisik/alat pulih.
Tindakan operator berikut: kumpulkan log dan status akhir tiga ALAT,
inspeksi koneksi USB COM7 saat IDLE, jalankan uji prospektif; jangan
mempromosikan incomplete menjadi 900 baris valid.

## 19 Oktober — receiver tiga alat sekaligus, belum diuji fisik

`scripts/multi_device_receiver.py` mendukung tiga adaptor USB serial pada
Windows (contoh COM5/COM6/COM7), memetakan satu proses per instrument ke
`data/raw/devices/ALAT_1`, `ALAT_2`, `ALAT_3`. USB serial unik, jika
tersedia, dipakai untuk mempertahankan identitas alat meskipun nomor COM
berubah; mapping manual awal tetap wajib dicek. Parent memegang lock
single-device v4 untuk mencegah receiver baru saling berebut COM, dan
preflight read-only menolak proses receiver lama yang masih berjalan.
CSV final/incomplete, baseline, status, dan log tiap alat dipisah. File dari
tiga alat tidak digabung/ditimpa. Paket portabel baru v5 di `dist/`.
**QA offline: 3 proses simultan, masing-masing 900 sensor rows, identik
sample/batch, PASS tanpa membuka port serial fisik.** Next step adalah
verifikasi pada laptop Windows 10 dan 3 perangkat nyata, setelah receiver
lama ditutup dalam kondisi IDLE. Panduan `windows_receiver/README_THREE_DEVICES.md`.

## 18 Oktober — diagnosis receiver ganda dan pemulihan CSV

Audit pasif Windows mendapati adaptor FT232R (`0403:6001`) pada COM4, tetapi
receiver repo berjalan dengan argumen `--port COM5` dan gagal mengakses COM5.
Ada tiga instalasi receiver (lima proses Python, sebagian launcher); portable
lama berhasil menangkap 3 sesi `L-MING_B50*` masing-masing 900 sampel dan
menyimpannya ke folder `data/raw/` dalam direktori **instalasi Downloads**,
bukan checkout repo. Portable v3 lain mencoba membuka COM4 namun mendapat
`Access is denied`. Ketiga CSV diverifikasi validator 30 siklus dan SHA256,
lalu disalin aman ke `data/raw/` repo tanpa menghapus file sumber.

Shortcut Startup Windows yang saling bertabrakan dibackup, lalu diganti satu
shortcut repo `--port auto` untuk **login berikutnya**; proses receiver yang
sedang berjalan tidak dihentikan. Paket Windows receiver v4 menambahkan mutex
satu instance per sesi Windows, status lokasi output, diagnostik read-only,
dan alat pemulihan no-clobber. Build/QA offline PASS; **live capture setelah
penggantian startup belum diuji**. Laptop Windows 10 yang sebelumnya gagal
enumerasi USB tetap memerlukan diagnosis FTDI terpisah. Detail:
`docs/reports/2026-10-18_WINDOWS_RECEIVER_RECOVERY_AND_STARTUP_QA.md`.

## 14 Oktober — Stage11 provenance + split gate + benchmark (offline)

**Audit ulang malam 14 Oktober WIB:** `stage11_quality_review.py` memeriksa
89 CSV, menandai 8 berkas berulang pada sel kode/batch dan 14
berkas interval sampling untuk review; tidak ada otomatis
eksklusi, relabel, atau perubahan raw. Registri blind kini wajib
UUIDv4 acak; ekspor fitur blind diurutkan berdasarkan ID acak
untuk mengurangi kebocoran urutan pengambilan.
**Blind final riil tetap belum tersedia.**

Tanpa mengubah firmware RC2, tidak membuka serial/G3, dataset
Stage2 canonical 89 CSV dipastikan SHA256 cocok: 83 `DEV_ONLY`
berlabel fisik belum diverifikasi, 6 clean-air excluded.
Tidak ada spesimen independen/prospective final test baru.
Implementasi Stage11 menyediakan registri metadata fisik,
hash gate, larangan lot/spesimen/sesi/hari lintas partisi,
ekspor fitur holdout tanpa label/filename dan custodian-only
blind scoring (future). Benchmark development 4 model dan
4 batch selesai, tetapi **BUKAN blind**. Actual blinded
prospective test **BLOCKED**, model **NO-GO/N/A**.
Laporan: `docs/reports/2026-10-14_STAGE11_DATASET_PROVENANCE_INDEPENDENT_SPLIT_BLIND_PROTOCOL.md`.


## 14 Oktober — Stage10 audit independen kelayakan model (NO-GO)

**G3 tetap PASS, firmware RC2 tidak diubah dan tidak ada
pengujian perangkat pada tahap ini.** Berdasarkan 83 akuisisi
historis, RF/LDA Roast Level hanya 45/83 benar (54,2%) pada
LOBO; tes sensitivitas leave-sample-code-out 49,4%/51,8%.
Origin RF: **21/83 benar (25,3%)**, sembilan origin dan
sebagian kelas masih minim spesimen. Lima udara bersih
dipaksakan sebagai light roast oleh model closed-set tanpa
unknown gate, bahkan dengan confidence tinggi. Probabilitas
belum terkalibrasi dan fitur kandidat Stage3 82 berbeda dari
20 fitur lama pada source on-device MCU. **AI NO-GO / N/A**.
Laporan dan gerbang: `docs/reports/2026-10-14_AI_MODEL_READINESS_INDEPENDENT_AUDIT_STAGE10.md`.


## 14 Oktober 18:23 — G3 RC2 lima siklus fisik QA PASS

**Konfirmasi operator setelah run RC2:** Nextion mencapai
`Test Complete – AI Result`; Roast Level, Coffee Origin,
dan Roast Probability semuanya tetap `N/A`. Observasi ini
melengkapi bukti 150 sampel dan `ACQ_COMPLETE` Pi.
Status tetap **G3 akuisisi fisik PASS / AI NO_GO**.

**Pembaruan status terbaru (menggantikan G3 NOT RUN lama):**
setelah RC2 di-flash pada ATmega2560 dan USB kembali ke Pi,
listener read-only G3 menerima **150/150 sampel** lengkap
(125 purging, 25 collecting), 1 `EVT:AI_START`, 1 `ACQ_START`
diterima, 9 `PHASE_CHANGE`, 1 `ACQ_COMPLETE`.
`FW_HELLO` dan build ID `g3-rc2-20261014` cocok;
`physical_g3_complete_verified=true`, `COMPLETE_QA`,
exit code 0. FT232R stabil dan Pi `throttled=0x0`.
Status **G3 PHYSICAL ACQUISITION PASS untuk satu run**,
tetapi **AI tetap NO_GO / `N/A`**. Bukti:
`docs/reports/2026-10-14_G3_RC2_PHYSICAL_5_CYCLES_PASS.md`.


## 14 Oktober 17:28 — Firmware RC2 berhasil DI-FLASH ke PCB COM5

**Pembaruan ini menggantikan status 'RC2 belum flash' di bawah.**
`pio run -e mega2560 -t upload --upload-port COM5` berhasil:
MCU signature `0x1E9801` dan **34930 bytes of flash verified**.
Backup flash/EEPROM lama melalui bootloader disimpan **lokal saja**
di `results/firmware-backup-20261014/`; EEPROM pascaupload
**4096 bytes verified** cocok backup. Windows listener autosave
yang sebelumnya mengunci COM5 dihentikan dan belum di-restart.
**Tetap tertunda:** bukti runtime `FW_HELLO/ACQ_START` RC2,
pengujian G2/G3 fisik ulang, validasi model dan probabilitas.
AI Result tetap N/A/NO_GO. Bukti: `docs/reports/2026-10-14_RC2_FLASH_COM5_ATMEGA2560_VERIFIED.md`.


## 14 Oktober — RC2 firmware/menu/host dibekukan (software saja)

Enam tombol utama Nextion diaudit: Start Test, Take Data,
Settings, History, Calibrate, Exit. Event HMI dan handler
firmware cocok secara statis; navigasi selama akuisisi aktif
sekarang ditolak. Tampilan AI diperjelas menjadi `N/A` karena
model valid belum tersedia, bukan mengisi prediksi palsu.
Firmware source menandai `FW_HELLO` serta `ACQ_START` dengan
build `g3-rc2-20261014`. Listener Pi menyediakan penanda siap,
durasi 240 detik, serta menuntut identitas dan 5 siklus valid
untuk QA G3. Regresi offline lulus; **belum flash MCU / belum
uji fisik RC2 / belum membuktikan EEPROM dan flash aktual**.
Laporan: `docs/reports/2026-10-14_RC2_AUDIT_MENU_NEXTION_G3_AI_RESULT.md`.
Snapshot: `pre-onsite-software-2026-10-14-rc2`.


## 14 Oktober — G3 nyata pasca-reboot: START terdeteksi, QA gagal tertutup

**Update observasi operator 16:45 WIB:** Nextion menampilkan
lima siklus selesai dan halaman `Test Complete - AI Result`
(Roast Level, Coffee Origin, Roast Probability). Ini adalah
**observasi HMI**, bukan data `ACQ_COMPLETE` yang diterima Pi.
Pada source RC1, nilai roast/origin/confidence belum tervalidasi
dan diset `N/A`; grafik probabilitas direset ke 0. Nilai
aktual LCD belum disebut oleh operator. Status tetap
**HMI complete (operator) / Pi G3 FAIL_CLOSED / AI NO_GO**.

Operator menekan START AI TEST setelah listener Pi read-only
benar-benar aktif. Pi menangkap `EVT:AI_START` (1),
`EVT:TEST_START` (1), `ACQ_START` (1), `PHASE_CHANGE` (6),
99 frame sensor valid serta 80 frame `phase=idle` yang
tidak memenuhi skema. **ACQ_START ditolak `ai_test_label_leakage`**,
sehingga host melaporkan `NOT_STARTED`; ini *bukan* berarti
tombol tidak ditekan. Firmware `FW_HELLO` RC1 tidak
teramati. USB FT232R tetap tersambung, `throttled=0x0`.
Durasi pendengaran 180 detik tidak menyediakan bukti
`ACQ_COMPLETE` atau lima siklus lengkap. Keputusan
`G3_NOT_PASS` dan AI `N/A`. Bukti, SHA256 dan diagnosis:
`docs/reports/2026-10-14_G3_SUPERVISED_AFTER_REBOOT_START_DETECTED_FIRMWARE_CONTRACT_FAIL.md`.

## 14 Oktober — P0 software freeze untuk persiapan bench

Enam masalah hasil audit telah diperbaiki dalam **source**
dan lolos QA offline Windows; parser/framer Pi yang baru
telah disinkronkan dan lolos regresi Pi. Validator menolak
indeks hilang atau urutan fase salah. Data B32+ 88 valid,
1 historical clean-air known-invalid excluded, 0 unexpected.
LCD collector memutus sesi lama sebelum mode berbeda dan
mengkarantina error. Collector manual butuh `--arm-hardware`
dan mempublikasikan CSV final hanya jika QA lengkap.
Firmware source menyiapkan `FW_HELLO`, **binary MCU tetap
belum dikonfirmasi/di-flash**. Freeze: tag
`pre-onsite-software-2026-10-14-rc1`, manifest pada
`docs/releases/2026-10-14_pre-onsite-rc1.json`. Test fisik
G3 tetap INCONCLUSIVE; AI N/A/NO-GO.

## Milestone Tahap 8+9 — integrasi software byte-stream + preflight hardware pasif

14 Oktober 2026: jalur **sintetis** UART byte stream dari
CSV asli B33 → `SerialLineFramer` Pi → `LegacySessionBridge`
→ Stage6 gate diuji end-to-end menggunakan 15 fault/success
cases. **2 COMPLETE_QA, 10 FAIL_CLOSED, 3 NOT_STARTED**;
output AI semua N/A, nol byte dikirim ke MCU dan nol aktuasi.
Reader Pi kini menghentikan `ACQ_START` kedua ketika sesi
pertama masih aktif dengan satu `SESSION_FINAL FAIL_CLOSED`.
QA Windows dan Pi PASS; checksum kode matched.

Stage9 *hardware identity passive* di Pi lewat udev/sysfs:
FT232R `A10KMM3S`, VID:PID `0403:6001`, driver `ftdi_sio`,
symlink by-id → `/dev/ttyUSB0`, port character device,
fuser no visible owner, `throttled=0x0`: **PASS IDENTITY ONLY**.
Tidak ada serial open, reset, flash, perintah Nextion,
EEPROM, pompa/valve, sampel fisik baru, atau validasi power
VBUS/backfeed. G3 hardware tetap **INCONCLUSIVE**, AI NO-GO.
Laporan: `docs/reports/2026-10-14_TAHAP8_9_TRANSPORT_E2E_AND_PASSIVE_HARDWARE_GATE.md`.

## Remote unattended QA — 14 Oktober 2026 sekitar 05:34–05:37 WIB

User mengonfirmasi **Pi dan PCB custom menyala tetapi tidak ada
operator di depan alat**; tidak ada supervisi pompa/valve.
Maka tidak dijalankan START AI TEST, serial command, flashing,
GPIO, reboot, atau pembukaan USB/tty yang berisiko auto-reset.
Preflight non-invasif: Pi via SSH OK, FT232R
`0403:6001 A10KMM3S` tetap ke `/dev/ttyUSB0`, `fuser`
kosong, getty/ModemManager inactive, throttling `0x0`,
tidak ada log kernel disconnect baru yang terlihat.

Offline: regresi Stage1/Stage6/Stage7/Stage8 Windows–Pi
PASS. CLI `replay-csv` di Pi memakai CSV existing
`data/raw/D-GAW_B33.csv` (SHA256
`d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`)
memberi **`COMPLETE_QA`, 151 sampel, AI `N/A`**. Nominal 150
false bukan alasan klaim 150; kriteria setiap fase/siklus
lolos sehingga replay QA COMPLETE. `hardware_serial_opened=false`
dan model promotion tetap NO-GO.

Peningkatan listener: agregat `acq_start_contract_outcomes`
(`accepted`, `ai_test_label_leakage`, `bad_start_contract`,
`other_rejection`). Test mensimulasikan metadata label
yang nyata-nyata tercetak pada `AI_TEST` source pra-`75cb38a`
tanpa menyimpan nilai label. Checksums listener Windows–Pi
identik. **G3 live INCONCLUSIVE**: perlu supervisi fisik
dan pembuktian firmware installed; jangan menafsir replay
sebagai uji hardware. Laporan:
`docs/reports/2026-10-14_TAHAP7_REMOTE_UNATTENDED_OFFLINE_QA.md`.

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
