# Catatan perubahan proyek

## 13 November 2026 — Konfirmasi LCD masih pada splash pascaperbaikan daya

- Mengunci observasi operator bahwa LCD PCB kedua
  tetap pada `Initializing Systems` meski
  suplai Raspberry Pi pulih.
- Memastikan secara offline bahwa `pSplash` HMI
  acuan tidak memiliki perpindahan `page pHome`
  mandiri; source mengirimkannya melalui
  `Serial2/9600` setelah sensor dan scheduler siap.
- Menyusun pohon diagnosis TXD2 → RX Nextion
  yang memerlukan pengukuran onsite untuk
  membedakan MCU, I²C dan wiring/HMI fisik.
- Tidak menjalankan flashing, EEPROM, serial TX
  ataupun kontrol aktuator; RF500 tetap ditahan.

## 13 November 2026 — Diagnosis ulang PCB kedua setelah PSU custom stabil

- Pi 5 boot baru: `get_throttled=0x0`,
  `EXT5V_V` lima kali di kisaran 5,11344–5,14560 V
  tanpa undervoltage terdeteksi.
- FT232R `A10KNJBL` terenumerasi di Pi pada
  `/dev/ttyUSB0`; serial passive 30 detik
  115200 baud, DTR/RTS false, RX=0 byte,
  TX=0 byte, tanpa disconnect baru.
- Raw UART dan metadata disimpan privat di
  `private/second_pcb_pi_readonly/`, bukan Git.
- Firmware fisik MCU belum teridentifikasi;
  kontrak startup Nextion dan build RF30 hanya
  PASS offline. RF500 live tetap ditahan.
- Laporan: `docs/reports/2026-11-13_SECOND_PCB_POST_POWER_RECOVERY_DIAGNOSIS.md`.

## 13 November 2026 — Pemeriksaan ulang PSU custom 5V pada kondisi idle

- Mendokumentasikan konfirmasi operator: daya Pi berasal
  dari power supply 5 V custom; indikator merah tidak berkedip.
- Melakukan delapan pembacaan `EXT5V_V` PMIC Pi secara read-only
  (minimum 4,93522 V; maksimum 4,97408 V; rata-rata 4,96738 V).
- Status `get_throttled` tetap `0x50000`, sebagai bukti
  kejadian startup historis; tidak menunjukkan undervoltage
  aktif selama pemantauan idle.
- Pengujian startup di bawah beban, MCU/Nextion dan RF500 live
  tetap memerlukan inspeksi onsite dan persetujuan.
  Tidak ada penulisan firmware, EEPROM atau konfigurasi Pi.
- Laporan:
  `docs/reports/2026-11-13_SECOND_PCB_POWER_RECHECK_CUSTOM_5V.md`.

## 13 November 2026 — Hentikan diagnosis aktif setelah temuan daya Pi

- Periksa read-only kondisi Pi/USB pada tahap
  tindak lanjut PCB kedua, tanpa membuka serial.
- Temuan: `throttled=0x50000` dan dua kejadian
  `Undervoltage detected!` pada journal boot.
- Tetapkan STOP untuk hardware/flash/EEPROM,
  serta tuntut inspeksi onsite suplai, RESET dan
  potensi konflik/backfeed sebelum uji selanjutnya.
- Tidak ada firmware, layanan, data, HMI ataupun
  konfigurasi permanen Pi yang diubah.
- Laporan:
  `docs/reports/2026-11-13_SECOND_PCB_POWER_STOP_CONDITION.md`.

## 13 November 2026 — Identifikasi pasif PCB kedua dan akar masalah splash

- Membaca laporan preflight PCB kedua, memverifikasi
  kondisi SSH, catu Pi, FT232R `A10KNJBL`, by-id
  `ttyUSB0`, dan absennya pemegang port.
- Menambahkan listener `pi_second_pcb_passive_id.py`
  dan QA no-TX; durasi 45 detik, UART0 115200,
  DTR/RTS false sebelum open, tanpa reset sengaja.
- Pembacaan langsung selesai **0 byte**; log mentah
  dan metadata di `private/second_pcb_pi_readonly/`,
  hash cocok, tanpa USB disconnect baru.
- Mengonfirmasi firmware source diam pada IDLE;
  identitas firmware terpasang masih UNKNOWN.
  Audit jalur `pHome`, potensi hang I²C sebelum
  scheduler, HMI 12 halaman/23 event dan image RF30.
- RF500 hanya dinyatakan staged; belum diaktifkan,
  tidak ada flash/EEPROM write, tidak ada operasi aktuator.
  Laporan:
  `docs/reports/2026-11-13_SECOND_PCB_FIRMWARE_ID_AND_ROOT_CAUSE.md`.

## 13 November 2026 — Alternatif COM11 bootloader + UART RX probe

- Membuat dan menguji `com11_alternative_bootloader_probe.py`
  dengan pengamanan identitas FT232RL dan batas waktu
  14 detik per profil: `arduino/115200` serta
  `wiring/57600` keduanya timeout.
- Membuat probe Windows RX-only 8 detik,
  `com11_uart_readonly_diagnostic.py`:
  RX = 0 byte, TX = 0 byte, tidak flash/EEPROM.
- Pengujian mock mendukung fail-closed dan
  menguji tidak ada perintah UART TX pada probe RX.
- Tidak ada programmer ISP USB terdeteksi.
  Jalur FT232RL ke ISP belum dapat dibuktikan;
  alternatif hardware memerlukan akses pin
  RESET/MOSI/MISO/SCK yang benar.
- Bukti hardware disimpan di direktori privat
  `private/com11_second_pcb_deployment/`,
  tidak masuk Git.
  Laporan: `docs/reports/2026-11-13_COM11_BOOTLOADER_ALTERNATIVE_PROTOCOLS_AND_UART_RX.md`.

## 13 November 2026 — RF30 guarded COM11 deploy dan pemeriksaan Pi

- Menambahkan `com11_rf30_verified_deploy.py` dengan pin identitas
  FT232RL, validasi image, guard receiver/dataset, pembacaan
  signature, backup asli lengkap, dan tahap upload/verify kondisional.
- Menambahkan mock QA termasuk timeout signature, backup gagal,
  backup Flash yang tidak lengkap, identitas salah, dan jalur
  sukses simulasi; tidak pernah menjalankan flash saat QA.
- Percobaan hardware di COM11 berhenti saat bootloader
  `stk500v2_ReceiveMessage(): timeout` (20 detik).
  Backup dan upload tidak dilakukan; evidence ditulis
  di `private/com11_second_pcb_deployment/`, di-ignore Git.
- Raspberry Pi kembali dapat diakses via Tailscale, hash model
  RF500 dan kandidat RF30 di staging sesuai; USB FT232RL
  tidak terpasang ke Pi karena sedang di laptop.
  Tidak ada aktivasi bridge atau akuisisi fisik.
- Laporan: `docs/reports/2026-11-13_COM11_RF30_BOUNDED_DEPLOYMENT_ATTEMPT.md`.

## 13 November 2026 — Migrasi konfigurasi aktif ke COM11

- Menetapkan COM11 sebagai port upload/monitor PlatformIO
  untuk kedua environment, tanpa menjalankan upload.
- Skrip manual collector, contoh dashboard, pemasangan
  receiver single-device dan pemeriksaan USB diperbarui.
- Pemeriksaan USB read-only memakai ID FT232RL
  `A10KNJBLA`; skrip test membuktikan serial
  COM5 perangkat lain tidak dapat salah dipilih.
- Shortcut Startup Windows existing dicadangkan,
  dipin berdasarkan USB serial, tidak dijalankan
  karena bootloader ATmega belum respons dan
  receiver dapat memonopoli COM11.
- Tidak menyentuh firmware, EEPROM, HMI, CSV,
  atau konfigurasi receiver tiga perangkat.
  Laporan: `docs/reports/2026-11-13_COM11_ACTIVE_CONFIGURATION.md`.

## 13 November 2026 — Audit ulang komprehensif FT232RL onboard

- Memperbaiki interpretasi topologi: FT232RL merupakan
  **IC onboard PCB kedua**, bukan modul FT232RL eksternal.
  Enumerasi COM11 tidak sama dengan MCU siap diprogram.
- QA build RF30, checksum kandidat, Nextion dan parser
  900 ADC PASS offline; upload tidak dijalankan.
- Menemukan status Pi 5 offline di Tailscale pada pemeriksaan
  terbaru; diagnosis Pi live kini terpisah dari diagnosis
  bootloader ATmega dan startup Nextion.
- Membukukan risiko `upload_port=COM4` yang stale,
  receiver Windows yang dihentikan, serta origin/confidence
  yang memang N/A oleh desain RF500 kandidat.
- Rencana diagnosis net DTR#/RESET dan ISP serta syarat
  backup khusus PCB kedua: lihat
  `docs/reports/2026-11-13_FULL_AUDIT_SECOND_PCB_ONBOARD_FT232RL_COM11.md`.

## 13 November 2026 — COM11 Windows terdeteksi, bootloader belum respons

- FT232R pada PCB kedua pindah ke COM11 Windows
  (FTDI `0403:6001`, serial `A10KNJBLA`).
- Receiver otomatis PID 15160 dihentikan sesudah
  memeriksa folder akuisisi sementara kosong;
  receiver tetap berhenti untuk mencegah perebutan COM11.
- Upaya AVRDUDE 6.3 membaca signature ATmega2560
  dengan `wiring/115200` pada COM11 masih timeout.
  Tidak ada upload firmware/EEPROM/HMI dan data
  maupun konfigurasi PCB lama tidak disentuh.
- Laporan:
  `docs/reports/2026-11-13_COM11_WINDOWS_FT232R_BOOTLOADER_TIMEOUT.md`.

## 12 November 2026 — Release gate PCB kedua diuji langsung di Pi

- Menambahkan skrip status release RF30 fail-closed
  dengan verifikasi checksum model, firmware, FT232R,
  tool programmer, power dan bukti backup asli PCB kedua.
- QA mock PASS; skrip terpasang pada Pi, output live
  `NO_GO_PHYSICAL_DEPLOYMENT` karena backup dan
  signature MCU kedua belum terverifikasi.
- Memperbaiki dokumen arsitektur agar tidak
  menyebut firmware SVM30 milik PCB lama sebagai
  firmware yang terpasang di PCB kedua.
- Firmware dan EEPROM tidak disentuh; bridge AI
  tetap belum diaktifkan. Laporan:
  `docs/reports/2026-11-12_SECOND_PCB_RELEASE_GATE_FINAL.md`.

## 12 November 2026 — Permintaan deployment RF30 PCB kedua, signature masih timeout

- SSH Pi, FT232R, checksum kandidat RF30 dan model RF500
  berhasil diverifikasi ulang.
- Satu percobaan read-only identifikasi bootloader
  `wiring/115200` tetap timeout (exit 124, 15 detik).
  Tidak ada operasi flash/EEPROM karena programmer tidak
  berhasil membaca signature.
- `lsusb` tidak menampilkan ISP USB programmer lain;
  tidak ditemukan backup PCB kedua di lokasi Pi yang diperiksa.
  Aktivasi bridge RF500 ditahan sampai MCU terverifikasi.
- Detail:
  `docs/reports/2026-11-12_SECOND_PCB_RF30_UPLOAD_ATTEMPT_BOOTLOADER_UNRESPONSIVE.md`.

## 12 November 2026 — Programer Pi siap; signature PCB kedua belum terbaca

- `avrdude` 7.1 dan pustaka arm64 disiapkan secara
  terisolasi di staging Pi tanpa sudo/instalasi sistem.
- Satu percobaan `wiring` 115200 read-only dibatasi
  20 detik: `stk500v2_recv() timeout`, exit 124;
  MCU tidak memberi signature; tidak ada backup atau flash.
- Pi/FT232R tetap terhubung sesudah uji, tanpa indikasi
  error xHCI baru. Firmware RF30 dan model RF500
  tetap staged dengan checksum cocok.
- **NO-GO** upload; perlu konfirmasi DTR/reset,
  wiring Serial0, bootloader/ISP serta backup Flash/EEPROM
  spesifik PCB kedua. Laporan:
  `docs/reports/2026-11-12_SECOND_PCB_AVRDUDE_SIGNATURE_TIMEOUT_NO_FLASH.md`.

## 12 November 2026 — G2 PCB kedua dan kandidat RF30 startup guard

- Membaca FT232R PCB kedua selama 8 detik dengan izin
  operator: port berhasil dibuka, **0 byte RX**, tanpa
  gangguan kernel USB baru; tidak ada perintah TX.
- Memperkuat startup profil RF30 host: timeout Wire
  25ms dan tanpa scan I²C penuh sebelum scheduler HMI.
  Build default dan SVM30 tetap tak berubah perilakunya.
- RF30 build 35.770 B Flash / 3.917 B SRAM global dan
  regresi offline lulus. Bundle privat khusus PCB kedua
  disalin ke Pi dengan hash identik, **tidak di-flash**.
- Firmware/EEPROM PCB kedua belum di-backup; rollback
  COM5/PCB lama tidak berlaku. Live RF500 masih blocked.
- Laporan:
  `docs/reports/2026-11-12_SECOND_PCB_G2_RX_ZERO_BOOTGUARD_RF30_STAGED.md`.

## 12 November 2026 — Koreksi identitas PCB dan diagnosis pasif startup Nextion

- Operator memastikan FT232R Pi terhubung ke PCB ATmega2560
  **berbeda** dari perangkat yang sebelumnya menjalankan SVM30.
- Nextion PCB kedua masih `Initializing Systems`; host USB
  terdeteksi normal, firmware MCU belum diketahui.
- Menelusuri source startup, I²C scan dan peralihan `pHome`;
  tidak dapat menisbahkan masalah ke RF500 atau FT232R saja.
- Backup/rollback COM5 PCB lama **tidak boleh dipakai** sebagai
  backup PCB kedua. Tidak ada akses serial, flash, reset atau
  pengendalian aktuator.
- Laporan: `docs/reports/2026-11-12_SECOND_PCB_NEXTION_INITIALIZING_REMOTE_PREFLIGHT.md`.

## 12 November 2026 — Pi 5 pulih setelah reboot; readiness RF500 diuji ulang

- SSH/Tailscale pulih; boot baru ditemukan setelah Pi sempat offline.
- Tujuh sampel observasi pasif dalam sekitar 90 detik
  menunjukkan FT232R `A10KNJBL` dan daya Pi terdeteksi
  konsisten tanpa flag undervoltage. Penyebab restart belum diketahui.
- Host RF500 readiness dan replay 900 sampel menggunakan model asli
  PASS; ACK masih simulasi, serial tidak dibuka.
- **Flash RF30 ditahan**: jalur FTDI Pi berbeda dari Windows COM5,
  Windows tanpa COM, programmer Pi belum tersedia dan izin
  flashing spesifik belum diperoleh.
- Laporan: `docs/reports/2026-11-12_PI5_POST_REBOOT_RF500_READINESS.md`.

## 12 November 2026 — Koreksi status koneksi Pi setelah pemeriksaan FT232R

- Pukul ±15:42 WIB, Pi tidak lagi dapat dijangkau via SSH,
  ping maupun Tailscale. Tidak ada pembacaan serial atau
  log kernel setelah putus jaringan, sehingga penyebab
  belum diketahui.
- Status kesiapan poin 1 diperbarui **PARTIAL/BLOCKED**:
  USB stabil hanya selama observasi pasif sebelumnya;
  koneksi Pi live tidak stabil/tersedia saat pemeriksaan akhir.
  Poin 2 tetap **NO-GO** untuk flash.
- Catatan kronologis ditambahkan pada laporan FT232R.

## 12 November 2026 — Uji pasif FT232R sebelum RF500 Pi Return

- Lima sampel pemeriksaan Pi selama sekitar 61 detik:
  FT232R `A10KNJBL` tetap `/dev/ttyUSB0`, daya
  `throttled=0x0`. Log boot tanpa `disconnect` hingga
  15:38:45 WIB; tidak ada serial-open maupun aksi fisik.
- Build kandidat RF30 return dan delapan QA offline PASS;
  checksum HEX RF30 dan rollback SVM30 cocok dengan manifest.
- Flash RF30 tetap **NO-GO** sampai identitas adaptor/MCU,
  SOP daya/rollback dan izin spesifik dikonfirmasi. Uji USB
  saat data live belum dilakukan.
- Laporan: `docs/reports/2026-11-12_RF30_PI_FT232R_PASSIVE_STABILITY_CHECK.md`.

## 12 November 2026 — Cabang cadangan standalone dan staging RF500 Pi

- Menyimpan skema ATmega standalone SVM30 pada
  branch baru `backup/atmega-svm30-standalone-20261112`
  tanpa mengubah working tree pengguna.
- Verifikasi Pi SSH melalui host key tersimpan,
  model RF500 (hash pinned) serta replay
  900-sampel + ACK simulasi **PASS**.
  Memasang pyserial 3.5 hanya di venv Pi;
  staging skrip readiness dengan checksum terverifikasi.
- FT232R Pi sempat tidak terdeteksi lalu muncul
  sebagai `/dev/ttyUSB0`; **tidak dibuka**,
  belum ada pembuktian serial live.
- Mengemas firmware kandidat RF30 Pi Return,
  35.748 byte Flash, 3.917 byte SRAM global,
  serta image rollback SVM30 tetap privat.
  Tidak mengubah firmware fisik, EEPROM, Nextion,
  layanan produksi, atau port USB aktif.
- Menambahkan readiness fail-closed
  `pi_rf30_pi5_readiness.py` dan test,
  pemeriksaan image RF bootloader-safe dan test.
- **RF500 Pi belum dipasang ke MCU**:
  butuh SOP jalur programmer, upload satu kali,
  uji G2/G3 dan hasil pResult nyata.
  Laporan:
  `docs/reports/2026-11-12_RESTORE_PI5_RF500_STAGING.md`.

## 11 November 2026 — Uji kedua L-TOR benar, origin/probability belum diimplementasikan

- Pengujian fisik kedua untuk sampel L-TOR yang
  sama menampilkan LIGHT (sesuai label), sementara
  pengujian pertama menampilkan DARK (salah).
  Konsistensi hasil masih perlu ditingkatkan.
- Origin dan Roast Probability/Confidence masih
  N/A **sesuai desain firmware SVM30 standalone**
  yang hanya mengklasifikasikan roast dan tidak
  mempunyai model origin/probabilitas terkalibrasi.
- Dokumentasi observasi dan batas validitas
  diperbarui. Tidak melakukan reflash atau
  akses serial/EEPROM/Nextion TFT.

## 11 November 2026 — B6 LIGHT terdeteksi DARK

- Uji fisik berhasil memunculkan prediksi di LCD
  tetapi salah kelas: LIGHT→DARK.
- Audit replay 199 sesi menunjukkan 156 sesuai
  label dan dua kasus LIGHT→DARK; kesetaraan
  model Python–C++ pada 199 replay tetap 100%.
- Menambahkan analisis offline tanpa hardware
  untuk memeriksa confusion per kelas dan kasus
  error. Detail privat di private/.
- Belum ada fitur atau skor dari run fisik;
  belum ada root cause pasti. Tidak mengubah
  model atau melakukan reflash.
- Laporan:
  docs/reports/2026-11-11_B6_LIGHT_TO_DARK_CLASSIFICATION_INCIDENT.md.
- Klarifikasi origin operator: **L-TOR**. Pemeriksaan
  34 replay TOR mendapati **13/14 L-TOR sesuai LIGHT,
  1/14 MEDIUM, 0/14 DARK**. Kasus fisik L-TOR→DARK
  memerlukan diagnostik sensor/fitur, bukan remap kelas.

## 11 November 2026 — B6 COM5 upload SVM30 standalone sukses terverifikasi

- Setelah konfirmasi operator dan preflight COM5,
  checksum candidate+model serta backup,
  disiapkan rollback app-only dari Flash lama
  dengan batas bootloader `0x3E000`; image
  rollback **belum terbukti dapat direstore
  ke hardware**.
- Satu upload `avrdude` `-c wiring` / COM5
  / 115200 baud `-D` dengan image SVM30 final.
  Device signature `0x1e9801`; **50.006 byte
  Flash ditulis + 50.006 byte diverifikasi**,
exit code 0 dan durasi 24,27s.
- Firmware/model/rollback/log disimpan di
  `private/` tidak di-Git. Tanpa EEPROM write,
  TFT/Nextion upload, auto-retry, atau operasi
  pompa/valve melalui komputer.
- **B6 fisik 30 siklus dan kelas `pResult` belum
  teruji**, menunggu pemeriksaan pHome dan
  interaksi START AI TEST oleh operator onsite.
- Laporan: `docs/reports/2026-11-11_B6_COM5_SVM30_FLASH_VERIFIED.md`.

## 11 November 2026 — B6 COM5 Flash/EEPROM read-only backup

- Setelah izin pengguna dan konfirmasi `pHome` sebelumnya,
  receiver PID 14628 dihentikan secara spesifik ketika
  `data/raw/.incoming` kosong; autostart/data tidak berubah.
- Satu sesi `avrdude` no-write `-n` melalui COM5
  FT232R `A10KMM3SA` berhasil identifikasi ATmega2560
  `0x1e9801`, backup Flash/EEPROM. EEPROM 4096/4096
  byte, Flash Intel HEX mencakup prefix 261406/262144
  byte dan memangkas 738 byte terakhir (diasumsikan
  FF untuk interpretasi, **tidak diobservasi**).
- Menambahkan skrip backup guarded dan verifier
  checksum/cakupan Intel HEX + QA negative parser.
  Backup, avrdude log dan manifest disimpan privat.
- B6 physical AI test/flash masih **NO-GO** hingga
  bukti `pHome` pasca-reset, SOP power/recovery,
  dan izin spesifik upload. Tidak ada firmware/EEPROM
  yang ditulis.
- Laporan `docs/reports/2026-11-11_B6_COM5_FLASH_EEPROM_READBACK.md`.

## 11 November 2026 — Konfirmasi pHome operator dan B6 preflight ulang

- Operator mengonfirmasi Nextion sekarang sudah masuk
  `pHome` melalui PCB/COM5 (laporan visual, bukan
  serial read-back).
- Preflight B6 mendapat opsi
  `--operator-reported-phome` untuk mencatat bukti
  observasi operator secara eksplisit tanpa membuka COM.
  Uji delapan gerbang safety PASS, hasil tetap **NO_GO**
  dengan empat blockers: COM5 masih milik receiver,
  belum ada backup Flash/EEPROM, SOP daya/programmer
  belum sah, serta belum ada izin upload spesifik.
- Firmware dan model SVM30 tidak diubah atau di-flash.
  Laporan diperbarui pada
  `docs/reports/2026-11-11_B6_COM5_WINDOWS_PREFLIGHT.md`.

## 11 November 2026 — B6 preflight COM5 Windows, hardware NO-GO

- Memverifikasi COM5 FT232R serial `A10KMM3SA` melalui
  enumerasi Windows saja, **tanpa membuka UART**.
  Receiver lama PID 14628 masih connected ke COM5
  menurut status/log 15:16 WIB, tidak dihentikan.
- Checksum model SVM30 dan firmware standalone Intel
  HEX privat cocok; backup Flash/EEPROM, bukti Nextion
  `pHome`, SOP program/reset masih belum ada.
- Menambahkan preflight yang **tidak pernah membuka COM**
  dan 8 test gates safety. Status akhir **NO_GO**;
  belum ada flashing fisik atau uji 15 menit.
- Laporan `docs/reports/2026-11-11_B6_COM5_WINDOWS_PREFLIGHT.md`.

## 11 November 2026 — Integrasi standalone B4 dan QA B5 (B6 hardware NO-GO)

- Firmware ATmega main kini memiliki jalur compile-time gated
  `SMART_COFFEE_STANDALONE_SVM30=1`: reset fitur saat AI START,
  30 siklus × 25s purging+5s collecting, 900 ADC strict,
  30 fitur streaming, SVM final PROGMEM dan hasil `pResult`.
- Tanpa Pi/USB listener atau simpan CSV; event Start Take Data,
  baseline Record dan Result Save ditolak dengan pesan Nextion.
  Output `tRoast` Light/Medium/Dark atau N/A; Origin/
  Confidence N/A; desain HMI/Nextion tidak diubah.
- Build AVR standalone penuh PASS **50.006 B Flash /
  4.189 B SRAM global**; build default tetap 34.760B/
  3.899B. Diagnostic compiler memperkirakan 663B
  frame stack classifier, belum termasuk seluruh call
  stack/interrupt; pengukuran runtime 16MHz outstanding.
- Regresi firmware, kontrak Nextion, input buruk,
  ekstraksi/model parity lulus. Image Intel HEX dan
  model full disimpan privat, **tidak** di Git.
- B6 **BLOCKED** karena FT232R masih hilang di Raspberry Pi
  pada 15:41 WIB dan `pSplash` Nextion terakhir stuck.
  Tidak ada hardware reset/flash/serial open/aktuator.
- Laporan: `docs/reports/2026-11-11_B4_B6_SVM30_STANDALONE_INTEGRATION_QA.md`.

## 11 November 2026 — B1–B3 port SVM30 final ke C++ ATmega (offline)

- B1: hash sumber model asli dan fitur dipertahankan, 199
  golden reference dari helper Python asli + sklearn 1.7.2
  dikunci dalam `private/`, tidak dipublikasikan.
- B2: 30 fitur ADC absolut streaming, Welford/slope/STD
  populasi/area sesuai helper; 199/199 vektor lolos
  toleransi, 10 sesi rusak ditolak.
- B3: parameter SVM 125 support vector + scaler ke AVR
  PROGMEM (header privat); model libsvm RBF class vote
  memiliki **0 mismatch dari 199** dan skor pairwise max
  selisih **3,6055e-6**. Native QA dan build AVR
  terisolasi PASS (22.356B Flash / 431B SRAM global).
  Default firmware tetap nonaktif, build lama unchanged.
- Tidak ada flashing, pembacaan USB, pompa/valve, update Nextion,
  atau perubahan user `platformio.ini`. B0 dan B4–B6
  masih outstanding.
- Detail: `docs/reports/2026-11-11_B1_B3_EMBEDDED_SVM30_QA.md`.

## 11 November 2026 — rencana backup offline MCU SVM30 tanpa Raspberry Pi

- Menyusun rencana arsitektur `sensor → ATmega2560 (streaming 30 fitur +
  SVM RBF 125 SV di PROGMEM) → Nextion pResult`, tanpa Pi/USB listener
  atau penyimpanan CSV pada mode backup.
- Memeriksa model final dari pengguna (30 fitur, 125 SV,
  `gamma=0.1`), dan baseline compile-only firmware
  34.760B Flash / 3.899B SRAM. Belum ada model diekspor/di-flash
  atau prediksi fisik pada Nextion.
- Rencana memprioritaskan perbaikan boot splash stuck dan masalah
  xHCI sebelum pengujian hardware serta mengharuskan golden parity
  terhadap SVM Python sebelum model dipromosikan.
- Detail: `docs/plans/2026-11-11_BACKUP_STANDALONE_SVM30_ATMEGA2560.md`.

## 11 November 2026 — G2 USB gagal, FT232R disconnect/xHCI host died

- G2 satu kali dengan izin operator onsite/IDLE, by-id FT232R
  `A10KNJBL`, durasi batas 12 detik, 115200 baud, TX=0.
- Port serial gagal di-open `Errno 19` sebelum menerima UART.
  Kernel 11:59:29 WIB melaporkan `xHCI host controller not responding`
  dan `HC died; cleaning up`; FT232R hilang dari `lsusb`
  serta `/dev/ttyUSB0`. Pi tetap dapat diakses SSH.
- Tidak ada perintah START/aktuator atau flashing, dan **tidak**
  ada percobaan ulang pembukaan USB. Perlu pemeriksaan onsite
  kabel, PSU, VBUS/backfeed, ground, port FT232R sebelum G2 baru.
- Probe allowlist diperbarui untuk by-id serial FT232R `A10KNJBL`
  tanpa melonggarkan aturan izin, supervision dan source UART.
  Mock test PASS. Bukti: `docs/reports/2026-11-11_G2_USB_XHCI_FAILURE_1200.md`.

## 11 November 2026 — precheck G2 dan artefak final SVM 30 fitur

- Pi 5 Tailscale SSH/USB sysfs precheck PASS; terdeteksi FT232
  `A10KNJBL` di `/dev/ttyUSB0` dengan **disconnect/re-enumerate
  pukul 10.35 WIB**. G2 serial live tidak dijalankan karena
  SOP onsite serta review sambungan/identitas board belum lengkap.
- Enam file SVM pengguna dicatat berdasarkan SHA256; metadata model
  utama melaporkan SVM RBF **30 fitur/176 sesi** berbeda dari
  kandidat lokal 9 fitur/133 sesi. Joblib belum dieksekusi
  atau dipasang pada Pi. File bertanda `maybe` terpisah.
- Laporan: `docs/reports/2026-11-11_G2_PRECHECK_AND_USER_FINAL_SVM.md`.

## 11 November 2026 — SVM 9 fitur dilatih di Pi dan adapter balik diuji

- SVM RBF sekarang kandidat yang diminta pengguna; RF500 tetap
  di staging historis terpisah. Training 133 CSV a+b, holdout 66 CSV c;
  incomplete kept 4 dan duplikat 1 tidak digunakan.
- Fitur dihitung ulang dari 199 sumber SHA-pinned dan cocok dengan
  pengujian terdahulu; 9 fitur baseline-corrected pada TGS822,
  TGS2602, TGS816. `StandardScaler` training-only berada dalam
  pipeline, bukan fit ulang setiap AI Test.
- Model SVM dilatih langsung pada Pi scikit-learn 1.7.2:
  balanced accuracy CV lintas origin 54,69% dan testing c 65,27%.
  Model belum memenuhi validasi prospektif.
- Pi staging terisolasi `~/smart-coffee-stage7/svm30_staging/`;
  model binary tidak di-commit. Adapter `svm30_pi_return_bridge.py`
  memakai protokol `#rf30:TOKEN:roast;` yang sama agar kompatibel
  dengan MCU source, bukan RF classifier. Replay actual model 900
  frame pada cohort c PASS, ACK mock; fisik/serial TX NOT RUN.
- Detail: `docs/reports/2026-11-11_SVM30_PI_TRAINING_AND_NEXTION_CANDIDATE.md`.

## 11 November 2026 — RF500 model dijalankan offline di Pi dan protokol return

- SSH Tailscale ke Pi 5 berhasil dan preflight USB read-only memeriksa
  FT232R: serial saat ini `A10KNJBL`, bukan serial Oktober.
  Kernel mencatat disconnect dan reconnect; tidak dilakukan serial
  open, flash, reset, atau operasi aktuator.
- RF500 asli (SHA-pinned, 2,36 MB) dan metadata disalin melalui SSH
  ke staging terisolasi `~/smart-coffee-stage7/rf30_staging/`, **bukan Git**.
  Venv isolated dengan scikit-learn 1.7.2. Pengujian Pi pada CSV valid
  D-CAT_B70 (900 sampel) menghasilkan `dark` (RF vote fraction 1.0,
  belum terkalibrasi; bukan blind).
- Modul `rf30_pi_result_bridge.py` + `ai_rf30_return.h` menambahkan
  protokol kandidat Pi → MCU berupa token sesi, label roast,
  ACK/NACK dan timeout 30 detik. Integrasi HMI `pResult` secara
  source-only; origin/confidence tetap N/A. Safety flag
  `ENABLE_PI_RF30_RETURN=0` default, build bench =1 compile-only.
- Tes native parser, kontrak firmware, replay model asli di Pi ke
  `#rf30:B1F503A9:dark;` dengan ACK mock **PASS**.
  G2/G3 USB serial, flashing, hasil Nextion fisik dan validasi model
  prospektif **BELUM DIJALANKAN**.
- Detail: `docs/reports/2026-11-11_RF30_PI_REMOTE_STAGING_AND_RETURN_PROTOCOL.md`.

## 10 November 2026 — source Take Data dan AI Test disamakan menjadi 30 siklus

- Firmware source: kedua mode memakai konstanta 30 siklus yang sama,
  25 detik purging + 5 detik collecting, nominal 900 baris / 15 menit.
  `FW_HELLO` dan ID build diperbarui untuk membedakan firmware lama;
  progress/ETA `pTestRun` mengikuti 900 detik, `tFw` menunjukkan
  `DATA30-AI30`. HMI visual dan logika aktuator tidak diubah.
- Adapter Raspberry Pi Stage7 default 30 siklus, validasi per fase 25+5
  ketat, batas listener read-only 1.260 detik.
  Tes G3 5 siklus dipertahankan **hanya** sebagai fixture historis.
- Model RF500 tetap memakai 3 fitur ADC absolut dari sesi 30 siklus:
  tidak dilatih ulang, tidak di-Z-score/baseline correction, dan
  belum dipromosikan ke perangkat. Pi→ATmega→Nextion hasil AI belum
  aktif; `pResult` tetap N/A untuk mencegah prediksi tak terverifikasi.
- Laporan: `docs/reports/2026-11-10_TAKE_DATA_AI_TEST_30CYCLE_SYNC.md`.

## 10 November 2026 — kandidat RF500 30 siklus: adapter Pi dan kontrak LCD

- Terima kandidat model eksternal berformat joblib (500 pohon, tiga fitur ADC absolut), simpan manifest SHA256 dan skor yang **dilaporkan peneliti**, bukan klaim tervalidasi; model binary tidak disimpan di Git dan belum di-deserialize.
- Tambahkan `roast_rf30_pi_inference.py`: pengambilan 30 siklus (900 baris) ketat, urutan fitur persis helper sumber, tolak sesi incomplete/5 siklus, verifikasi metadata/hash sebelum mencoba menjalankan model.
- Tambahkan replay NDJSON firmware 30 siklus read-only dan tes positif/negatif tanpa port serial, tanpa HMI dan tanpa kontrol aktuator.
- Masalah integrasi dijelaskan: `Start AI Test` firmware sekarang hanya 5 siklus dan Pi→ATmega→Nextion belum memiliki handler hasil. Tidak ada perubahan firmware, wiring, Nextion atau keputusan GO produksi.
- Laporan: `docs/reports/2026-11-10_RF30_PI_NEXTION_INTEGRATION_CANDIDATE.md`.

## 14 Oktober 2026 — Stage11 pemisahan dataset & blind protocol

- Audit ulang source quality: flag review cadence 14 berkas,
  pengulangan kode UI/batch 8 berkas; tanpa relabel/exclusion.
- Opaque ID UUIDv4 diwajibkan untuk registry prospective dan
  blind feature export diurutkan menurut ID tersebut.
- Scorer yang disiapkan melaporkan recall per kelas dengan
  abstention sebagai salah, coverage, risk dan Brier multiclass
  deskriptif; origin final belum diuji.
- `test_stage11_development_benchmark.py` mengunci integritas
  grouped out-of-fold comparison. Regresi Stage2–6/10/11 PASS.

- 89 CSV frozen diverifikasi SHA256: 83 dev-only dan enam
  clean-air excluded, nol spesimen independen terverifikasi.
- `stage11_provenance_guard.py`: manifest + prospective registry
  and fail-closed lot/specimen/session/day split.
- `stage11_prospective_features.py`: keluaran 82 fitur hanya
  dengan opaque ID pada blind view (tanpa sumber/label).
- `stage11_development_benchmark.py`: empat comparator LOBO
  untuk pengembangan saja; hasil bukan blind.
- `stage11_blind_scoring.py`: scorer future custodian-only,
  hash freeze, abstention dan label vault terpisah.
- Test positif/sintetis dan negatif Stage11 PASS; data baru
  masih tidak ada sehingga real blind test **BLOCKED**.
- Tidak ada perubahan firmware RC2/G3/model produksi;
  preserve CSV mentah dan konfigurasi lokal.


## 14 Oktober 2026 — Stage10 audit kelayakan AI, device NO-GO

- Audit offline Stage3–Stage6: 83 akuisisi; 21 kode sampel,
  sembilan label origin; split yang tersedia belum membuktikan
  kemandirian spesimen atau ground truth yang diaudit.
- Evaluasi sensitivitas baru (holdout kode/origin), risiko
  confidence dan 5 sampel udara bersih memperjelas bahwa model
  belum siap. RF untuk origin benar 21/83, 5/5 udara bersih
  diprediksi sebagai light jika tanpa unknown gate.
- Pemeriksaan source: candidate Stage3 82 fitur belum cocok
  dengan legacy mean/max 20 fitur ATmega; daftar model lama
  masih mencantumkan MQ9.
- Implementasi `stage10_model_readiness_audit.py` + tes negatif,
  hasil immutable di `results/stage10_readiness_20261014_v2`.
- Tidak ada flashing/port serial/START/G3 ulang; tidak ada
  model baru yang diekspor. Stage6 NO_GO dan LCD N/A tetap.


## 14 Oktober 2026 — RC2 G3 supervised, akuisisi fisik PASS

- Konfirmasi lanjutan operator: Nextion selesai lima siklus
  hingga `Test Complete – AI Result`; Roast Level, Coffee
  Origin, dan Roast Probability tetap `N/A` sesuai gate AI.

- Pi menerima 150 sampel valid (125 purging, 25 collecting),
  `ACQ_START` diterima, 9 perubahan fase dan `ACQ_COMPLETE`.
- Marker firmware pada `FW_HELLO` dan `ACQ_START` MATCHED,
  satu `SESSION_FINAL.COMPLETE_QA` dengan status AI `N/A`.
- FT232R stabil, exit code listener 0, tidak ada perintah MCU.
- SHA256 bukti dicatat; G3 dinyatakan PASS **hanya untuk integritas
  akuisisi lima siklus fisik**, bukan evaluasi model.
- Laporan: `docs/reports/2026-10-14_G3_RC2_PHYSICAL_5_CYCLES_PASS.md`.


## 14 Oktober 2026 — RC2 flash fisik COM5 terverifikasi

- Target FT232R COM5 terdeteksi; `lcd_acquisition_service.py`
  PID 11144 yang mengunci port dihentikan tanpa dataset parsial aktif.
- ATmega2560 signature `0x1E9801` terverifikasi via bootloader.
- Sebelum flash, firmware/EEPROM lama dibaca ke backup lokal (tidak
  masuk Git). `pio run -e mega2560 -t upload --upload-port COM5`
  **SUCCESS, 34930 byte flash verified**.
- EEPROM setelah flashing cocok backup: **4096 byte verified**.
- G2/G3 firmware RC2 belum dijalankan; AI tetap N/A/NO_GO.
- Laporan: `docs/reports/2026-10-14_RC2_FLASH_COM5_ATMEGA2560_VERIFIED.md`.


## 14 Oktober 2026 — RC2 audit menu Home, G3, dan AI N/A

- Audit enam tombol Home: Start Test, Take Data, Settings, History,
  Calibrate, Exit; event HMI dan handler ATmega terbukti konsisten
  secara statis. Tidak ada perubahan desain Figma/HMI.
- `src/main.cpp`: marker `g3-rc2-20261014` pada FW_HELLO dan
  ACQ_START, navigasi saat akuisisi aktif ditolak; teks yang
  mengesankan AI sudah siap dikoreksi menjadi N/A/tidak tervalidasi.
- Pi G3 adapter: durasi 240 detik, penanda `G3_LISTENER_READY_USB_RX_ONLY`,
  pemeriksaan identitas tiap sesi serta complete fail-closed.
- Tes menu+G3 adversarial independen dan suite Stage0–9 offline PASS;
  dua firmware build SUCCESS, Nextion static 12 halaman/23 event PASS.
- Adapter Pi RC2 dan uji adapter disinkronkan dengan backup RC1;
  SHA256 identik, Pi Stage7/8 offline PASS, tanpa port serial dibuka.
- Sumber bukti HMI operator: lima siklus selesai, seluruh AI Result
  masih N/A (sesuai model NO_GO); Pi G3 lama gagal karena
  `ai_test_label_leakage` dan tidak merekam ACQ_COMPLETE.
- Freeze **source RC2**, bukan flash perangkat: tag
  `pre-onsite-software-2026-10-14-rc2`, manifest di
  `docs/releases/2026-10-14_pre-onsite-rc2.json`.
- Keamanan xHCI/VBUS dan firmware aktual masih gerbang onsite;
  flashing, kalibrasi, dan lima siklus ulang **tidak dilakukan**.


## 14 Oktober 2026 — Perbaikan enam P0 dan software freeze RC1

- Validator sensor CSV: gap indeks, urutan siklus/fase
  ditolak; 88 valid, 1 historical clean-air excluded
  invalid (`L-CAW_B34.csv`), 0 gagal tak terduga.
- Collector LCD: isolasi sesi labeled/AI_TEST, verifikasi
  START/COMPLETE, timeout/error quarantine, incomplete UUID.
- Parser serial bersama `serial_wire.py` dipakai Windows/Pi,
  termasuk framing lintas timeout dan batas ukuran pesan.
- Collector manual: perlu `--arm-hardware`, STOP pada
  sesi tidak lengkap, publish CSV hanya setelah validasi.
- Firmware source emits `FW_HELLO`, Pi listener membandingkan
  build/protocol; belum flash hardware.
- QA adversarial independen dan regresi Stage0–9 PASS,
  PlatformIO dua build SUCCESS, Nextion statis PASS,
  Pi offline regression PASS.
- Tag freeze `pre-onsite-software-2026-10-14-rc1`,
  manifest/checksum pada `docs/releases/2026-10-14_pre-onsite-rc1.json`.
- Hardware G3 tetap INCONCLUSIVE; AI NO_GO.


## 14 Oktober 2026 — Integrasi Tahap 8, gerbang pasif Tahap 9

- Implementasi `stage8_transport_integration.py` + uji:
  15 skenario arus byte UART simulasi dari ADC CSV asli,
  termasuk fragmentasi, timeout kosong, boot noise, idle,
  start label leakage, fault integrity, dan disconnect.
  Hasil Windows/Pi 2 COMPLETE, 10 FAIL_CLOSED, 3 NOT_STARTED.
- Fix Pi listener: START berulang ketika sesi aktif
  langsung abort `duplicate_start_while_active`, maksimal
  satu final pada satu capture; ditambah uji regresi.
- Implementasi `stage9_passive_readiness.py` + uji
  identitas FT232R by-id, udev VID/PID/serial/driver,
  pemilik port, dan Pi throttle, tanpa membuka serial.
- Firmware PlatformIO kedua environment SUCCESS, Nextion
  HMI 12 halaman/23 event PASS; QA Stage0/1/6/7/8/9
  software offline Windows dan Pi PASS.
- Laporan: `docs/reports/2026-10-14_TAHAP8_9_TRANSPORT_E2E_AND_PASSIVE_HARDWARE_GATE.md`.
- **G3 fisik tetap INCONCLUSIVE, VBUS/backfeed belum dibuktikan,
  promosi AI tetap NO-GO.** Tidak ada GPIO/flash/aktuasi.


## 14 Oktober 2026 05:34–05:37 WIB — QA remote unattended

- User remote, tidak berada di dekat alat: tidak menjalankan
  perintah yang memicu pompa/valve, serial open (berpotensi
  auto-reset MCU), flashing, atau reboot.
- Preflight read-only **tanpa membuka tty**: Pi SSH tersedia,
  FT232R `A10KMM3S` tetap pada `/dev/ttyUSB0`, tidak ada
  port owner, `get_throttled=0x0`.
- Regression suites Windows/Pi untuk Stage1/6/7/8 PASS;
  replay CSV existing pada Pi COMPLETE_QA 151 sampel,
  `hardware_serial_opened=false`, AI N/A.
- Tambah penghitung `acq_start_contract_outcomes`, mengenali
  penolakan `ai_test_label_leakage` firmware lama,
  `bad_start_contract`, accepted; hanya enum alasan statis,
  label kopi tetap tidak direkam. Tes regresi tiga kondisi PASS.
- G3 fisik masih INCONCLUSIVE. Evidence dan langkah
  keselamatan di `docs/reports/2026-10-14_TAHAP7_REMOTE_UNATTENDED_OFFLINE_QA.md`.


## 13 Oktober 2026 20:42–20:49 WIB — Fingerprint versi firmware runtime

- FT232R `A10KMM3S` read-only 15s: 5.026 byte, 38 baris;
  14 frame sensor-shaped ditolak karena `invalid_phase`.
- Perluasan diagnostik host: fase dalam enum tetap dan kategori
  `nextion_event` allowlist; tidak menyimpan data sensor mentah.
- Read-only 8s: 3.043 byte, 31 baris, 7/7 sensor-shaped
  memiliki `phase=idle`; USB tetap terenumerasi, tidak ada
  perintah aktuator/flash/perubahan EEPROM.
- Riwayat Git menunjukkan source sebelum `75cb38a` memang
  mengirim sensor JSON saat IDLE; firmware PCB diduga memakai
  implementasi sebelum perbaikan. Versi binary masih belum pasti.
- Regresi Windows–Pi, build firmware/Nextion offline PASS.
  Tidak ada pengujian lima siklus G3 baru; model tetap NO-GO.
- Rujukan: `docs/reports/2026-10-13_TAHAP7_P2_RUNTIME_FIRMWARE_DIAGNOSIS.md`.


## 13 Oktober 2026 sekitar 20:20 WIB — Pembacaan USB IDLE 15s

- Dengan izin operator, FT232R 115200 dibuka **satu kali**;
  menerima 5.026 byte, 37 baris (23 JSON, 14 non-JSON),
  tanpa USB disconnect. Tidak mengirim perintah MCU.
- Sebanyak 14 JSON memuat nama field sensor, tetapi 0 lolos
  validasi sampel aktif; 0 event akuisisi sesuai mode IDLE.
  Data mentah nilai sensor tidak direkam; status G3 tetap
  INCONCLUSIVE dan AI `N/A`.
- Menambah diagnostik host privacy-safe berupa agregat kode
  alasan penolakan frame sensor-shaped dan uji regresi.
  Tidak ada tes serial kedua ataupun flashing firmware.
- Evidence dan diagnosis: `docs/reports/2026-10-13_TAHAP7_P1_USB_IDLE_SCHEMA_15S_RESULT.md`.


## 13 Oktober 2026 20:09–20:12 WIB — Re-audit independen P0 pasca-reboot

- Re-check SSH pasif mengonfirmasi FT232R `A10KMM3S` masih
  terenumerasi dengan driver `ftdi_sio`; belum ada
  `USB disconnect` baru pada log boot yang diperiksa.
- SHA256 adapter pada Windows/Pi identik, bukti G3 Run02 di Pi
  tetap cocok dengan checksum historis.
- Tes Stage 7 Bridge/Adapter/USB Probe dan Stage 8 offline
  PASS di Windows dan Pi. Firmware `mega2560`/`nextion_test`,
  kontrak HMI, Stage 1 dan Stage 6 PASS offline Windows.
- Roadmap Tahap 7 dan status arsitektur diperbarui. USB open,
  stabilitas elektrik, firmware PCB aktual, G3 dan rilis AI
  **belum tervalidasi**; tidak ada tindakan hardware baru.


Dokumen ini mencatat milestone engineering yang relevan; detail teknis dan risiko tetap berada dalam laporan milestone terkait. Untuk riwayat perubahan terperinci, gunakan `git log` pada branch `wahyu`.

## 13 Oktober 2026 19:50 WIB — Enumerasi FT232R pulih setelah reboot Pi

- Operator melakukan reboot Raspberry Pi:
  boot baru terbukti pada **19:49:19 WIB**.
- FT232R `0403:6001` / `A10KMM3S`
  kembali terlihat di `lsusb` dan
  `/dev/ttyUSB0` (by-id terverifikasi);
  driver `ftdi_sio` aktif.
- Port bebas, getty/ModemManager inactive,
  Pi `throttled=0x0`; pemeriksaan
  **pasif tanpa membuka serial**.
- Penyebab disconnect sebelumnya belum
  pasti. Pembacaan JSON dan G3 fisik
  masih menunggu izin pengujian baru.

## 13 Oktober 2026 19:47 WIB — Reboot Pi tertahan autentikasi

- Operator memberikan izin reboot Pi.
  Sebelum percobaan, tidak ada proses
  akuisisi serial aktif; FT232R belum
  terdeteksi, power Pi `0x0`.
- `sudo -n -v` membutuhkan password;
  `systemctl --no-ask-password reboot`
  gagal karena butuh autentikasi interaktif.
- **Pi belum reboot**; tidak dilakukan
  bypass, reset USB, serial open, atau
  perubahan firmware. Tindak lanjut
  `sudo reboot` oleh operator secara lokal.

## 13 Oktober 2026 19:41 WIB — Cek ulang setelah restart operator

- Pemeriksaan pasif FT232R pada Pi
  dilakukan setelah operator melaporkan
  restart; **FT232R belum kembali**
  di `lsusb`, tidak ada `ttyUSB0`.
- Pi menunjukkan boot time `14:24`
  dan log kernel berakhir di USB
  disconnect `19:24:44`; Pi belum
  tampak di-restart sejak kejadian.
- Tidak ada percobaan serial open
  atau reset USB. Status tetap BLOCKED,
  perlu inspeksi kabel/jalur FT232R.

## 13 Oktober 2026 19:33 WIB — FT232R belum muncul kembali

- Operator menegaskan PCB custom dan
  Nextion menyala normal, kabel USB
  terpasang kedua ujungnya.
- Pi masih aktif, root hub USB
  muncul, tetapi FT232R `0403:6001`
  **hilang** dari `lsusb`,
  `/dev/ttyUSB0` dan sysfs.
  Tidak ada enumerasi ulang sesudah
  disconnect `19:24:44`.
- Ini pemeriksaan **pasif saja**,
  tanpa pembukaan port, reset driver,
  aktusi alat, flashing, atau
  percobaan ulang.
- Tindak lanjut dialihkan ke
  inspeksi fisik USB/power
  sebelum membuka serial lagi.

## 13 Oktober 2026 19:24 WIB — USB FT232R disconnect saat uji 15s

- Satu pembacaan read-only 15s mendapat izin
  pengguna; preflight FT232R dan uji offline PASS.
- `serial-readonly` gagal saat open dengan
  `Errno 19`; kernel menunjukkan kegagalan
  set termios/baud dan **USB disconnect**.
- Pasca-kegagalan, FT232R tidak lagi terdeteksi
  `lsusb`, tidak ada `ttyUSB0`, output JSON
  **tidak dibuat**, dan Pi `throttled=0x0`.
- Tidak mengirim perintah MCU, tidak mengulang
  port open atau menjalankan G3. Tahan
  pengujian hingga pemeriksaan USB/power
  bersama operator.
- Bukti dan batas diagnosis:
  `docs/reports/2026-10-13_TAHAP7_USB_READONLY_15S_DISCONNECT.md`.

## 13 Oktober 2026 malam — Konfirmasi G3 Run02 dan diagnostik skema JSON

- Operator mengonfirmasi START AI TEST
  ditekan dan kelima siklus Nextion
  berjalan sampai selesai **pada Run02**.
  Ketidaksesuaian pembacaan Pi masih
  belum terdiagnosis dari agregat lama.
- Menambah diagnostik `other_json_key_signatures`
  pada parser Pi untuk menangkap hanya
  key path JSON dan frekuensinya,
  dibatasi 8 skema/32 nama key; tidak
  menyimpan nilai sensor atau raw payload.
  Regresi offline/no-values **PASS
  Windows dan Pi**, skrip telah
  dideploy ke Pi dengan checksum.
- Tidak menjalankan ulang G3, USB port,
  flashing firmware, operasi aktuator,
  atau perubahan dataset/model.
  Pembacaan lanjut memerlukan izin baru.

## 13 Oktober 2026 — G3 USB Run02 di Raspberry Pi

- Setelah perbaikan reassembly serial,
  listener G3 kedua benar-benar
  berjalan di Pi pada USB FT232R
  115200 selama 180s (SHA256 source
  Pi sama dengan Windows; tes
  offline Pi PASS).
- Dibaca **52.224 byte, 303 nonempty
  chunk, 203 baris, 189 JSON valid,
  14 invalid/non-JSON**; **tidak
  ditemukan ACQ_START/COMPLETE ataupun
  sampel sensor sesuai skema**.
  Hasil `NOT_STARTED`, bukti asli
  `run02.json` di Pi beserta
  checksum tercatat pada laporan.
- Tidak ada uji ulang otomatis,
  flashing, perintah TX atau
  perubahan aktuator oleh listener.
  Menunggu konfirmasi aktivitas
  Nextion selama G3 Run02 sebelum
  memperluas diagnosis schema.

## 13 Oktober 2026 — Bug framing listener G3 diperbaiki

- Operator memastikan START AI TEST
  ditekan saat listener aktif dan
  lima siklus terlihat berjalan.
  G3 host tetap `NOT_STARTED`,
  jadi asumsi 'START belum ditekan'
  dikoreksi pada laporan historis.
- Memperbaiki `stage7_pi_adapter.py`:
  tambahkan reassembly byte sampai LF
  (tidak menganggap read timeout
  sebagai frame penuh), maksimum
  4096 byte per line, diagnostik
  jumlah byte/chunk/JSON/event/sampel
  tanpa menulis raw atau TX ke MCU.
- Regresi `test_stage7_pi_adapter.py`
  ditambah kasus potongan START
  dan replay data sensor asli
  151 sampel/five-cycle
  `COMPLETE_QA`: **PASS Windows**.
- **G3 belum diulang**; Pi runtime
  versi baru perlu diverifikasi
  sebelum izin satu sesi ulang.
  Firmware, CSV raw, aktuator dan
  AI model tidak diubah.
## 13 Oktober 2026 — G3 Nextion pertama, belum terverifikasi

- G3 listener USB fisik FT232R pada Pi
  berjalan 180s, setelah izin satu
  sesi melalui Nextion; operator
  diminta START AI TEST via LCD.
- Terdapat **304 nonempty read chunks**,
  namun `ACQ_START` valid tidak terdeteksi;
  `final.quality=NOT_STARTED`,
  `terminal_event_count=0`,
  `final.status=N/A`.
  **Tidak ada klaim sampel valid,
  lima siklus complete atau E2E PASS**.
- Port ditutup, Pi throttle `0x0`,
  raw CSV/firmware/aktuator tidak
  dimodifikasi/diperintah dari Pi.
  Minta konfirmasi operator mengenai
  START dan perilaku LCD sebelum
  uji ulang. Laporan:
  `docs/reports/2026-10-13_TAHAP7_G3_NEXTION_RUN01_INCONCLUSIVE.md`.

## 13 Oktober 2026 — Observasi alat setelah G2

- Operator mengonfirmasi **perangkat tetap
  normal seperti biasanya** sesudah
  pembacaan USB FT232R 12 detik.
- Tidak dilaporkan perilaku perangkat
  abnormal. Ini bukan bukti independen
  bahwa auto-reset MCU tidak terjadi.
- Status tetap: G2 USB RX **PASS**,
  validasi payload **PARTIAL**;
  G3 Nextion/pompa/valve **NOT RUN**.
  Hasil observasi ditambahkan pada
  laporan G2 tanpa membuka port lagi.

## 13 Oktober 2026 — G2 live USB PCB custom berhasil menerima bytes

- Berdasarkan persetujuan eksplisit operator,
  membuka FT232R by-id `A10KMM3S` pada
  Pi **115200 selama 12s** (bukan simulator).
  **4.313 byte, 33 baris** direkam dalam
  evidence JSON pada Pi, checksum SHA256
  ditulis di laporan.
- Klasifikasi: 14 other_json,
  5 i2c_found, 1 i2c_scan_done,
  13 invalid_json, **0 sensor samples**.
  Data I2C konsisten dengan startup;
  invalid mungkin banner plain text
  `printWelcome()` di source. Status
  `SERIAL_DATA_INCONCLUSIVE` dari
  classifier **tidak ditimpa**.
- Transport RX fisik **PASS**,
  validasi payload end-to-end belum
  PASS. Tidak ada perintah TX,
  operasi aktuator, pengaktifan
  akuisisi, atau AI model.
  Pi setelah uji throttling=0x0.
- Dokumentasi:
  `docs/reports/2026-10-13_TAHAP7_G2_USB_LIVE_RESULT.md`.
## 13 Oktober 2026 — Probe G2 USB PCB custom disiapkan

- Pembuat PCB menyatakan desain daya aman
  (attestation, tidak menggantikan
  pengukuran independen VBUS/backfeed).
- FT232R `A10KMM3S` by-id USB Pi
  terkonfirmasi, port/getty siap
  untuk uji G2 setelah kontrol
  keselamatan operasional terpenuhi.
- Menambah `scripts/stage7_usb_readonly_probe.py`
  dan `scripts/test_stage7_usb_readonly_probe.py`
  dengan opt-in G2 + IDLE + onsite,
  framing incremental, bounded
  read dan output evidence nonraw,
  tanpa serial write/aktuator/model.
  QA Windows + Pi **PASS**,
  skrip sudah ada di lingkungan Pi.
- **Port live belum dibuka**.
  G3 Nextion/aktuator tidak dijalankan;
  SOP dan laporan diperbarui.
## 13 Oktober 2026 — G0 foto USB PCB custom

- Audit foto Pi USB-A/USB-C dan PCB custom
  ATmega2560 (USB Type-B, DB9, sakelar
  dan adaptor daya terpisah). Jalur
  VBUS internal belum terlihat/diketahui.
- Pi USB enumerates FTDI FT232R `0403:6001`
  `ttyUSB0`; USB descriptor terdeteksi
  **Bus Powered 90mA** (nilai deklarasi),
  tanpa bukti electrical power isolation.
- **G0 partial/blocked**, G2/G3 NOT RUN.
  Checklist inspeksi PCB sisi dalam,
  pembagian rail USB/DC dan backfeed
  serta larangan membuka serial sementara
  diperjelas dalam SOP dan laporan baru.
- Tes UART testbed Arduino Mega yang
  sebelumnya sukses tetap valid sebagai
  **hasil board terpisah**, bukan klaim
  verifikasi PCB custom Smart Coffee.

## 12 Oktober 2026 — UART hardware testbed E2E PASS

- Pengguna memperbaiki wiring
  `HV1→Mega TX1 D18` dan
  `HV2→Mega RX1 D19`.
- Raw UART pada GPIO15 Pi sekarang
  menerima heartbeat JSON valid;
  ditemukan bug parser read_until
  yang menyalahkan potongan frame
  akibat timeout 0,5s untuk
  trafik Arduino periodik 1s.
- Mengganti receiver dengan
  incremental bounded LineFramer
  dan test fragmentasi/CRLF/oversize.
  **RX-only PASS** 5 frame/0 error.
- **PING/PONG E2E PASS**: Pi
  5 heartbeat + 1 PONG, USB Mega
  COM6 1 PING ACK. Uji 30s
  28 heartbeat/1 PONG/0 error.
- Menambah raw passive diagnostic,
  monitor USB laptop, ringkasan
  checksum evidence dan laporan
  post-rewiring.
- Hanya **Mega 2560 testbed
  dan Pi UART GPIO**; produksi
  Smart Coffee/PCB custom,
  Nextion, 115200 GPIO, AI
  belum dinyatakan PASS.

## 12 Oktober 2026 — UART testbed Mega 2560 ↔ Pi 5, diagnosis hardware

- Menambah proyek bench terisolasi
  `bench/mega_pi_uart/`: `platformio.ini`
  Mega, firmware heartbeat USB 115200/
  Serial1 GPIO 9600, parser Python
  Pi dengan timeout, limit frame, nonce
  PING allowlist, validasi seq/uptime,
  unit tests dan SOP.
- Upload sketch baru **HANYA ke Mega
  testbed COM6 CH340**, signature
  0x1e9801 tervalidasi dan flash
  **3212 bytes verified**; USB debug
  Mega mengirim HEARTBEAT 1–19.
- Pi SSH: `ttyAMA0` GPIO14/15
  UART aktif, serial-getty nonaktif.
  Pengujian RX 20s mendapatkan **0
  frame**. Pi diagnostic PING satu
  kali (bukan perintah aktuator)
  tidak mendapatkan PONG, dan
  Mega debug **tidak menerima PING**.
- **UART E2E testbed belum PASS**.
  Perlindungan 5 V→3,3 V dan
  sambungan level converter harus
  diperiksa secara fisik sebelum
  uji lanjut. Firmware utama
  PCB custom, konfigurasi lokal
  `platformio.ini` root, CSV/AI
  tidak diubah.
- Bukti JSON pada `bench/mega_pi_uart/evidence/`,
  laporan `bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`.
## 12 Oktober 2026 — Riset keamanan USB dan E2E offline Tahap 8

- Meneliti sumber resmi Raspberry Pi (batas
  USB dan larangan back-powering) dan FTDI
  FT232R (skema self-powered); port USB Pi
  normal bagi perangkat USB compliant.
  PCB ATmega custom dengan PSU berbeda
  **belum dibuktikan proteksi VBUS/backfeed**,
  sehingga G0 belum PASS, G2/G3 NOT RUN.
- SSH read-only Pi: `usb_max_current_enable=1`,
  `throttled=0x0`, FT232R `ttyUSB0`
  dan tidak terlihat overcurrent dalam
  potongan kernel log yang difilter.
  Tidak ada serial port opened.
- Menambah `scripts/stage8_offline_e2e.py`,
  regresi `scripts/test_stage8_offline_e2e.py`,
  dan bukti `results/stage8_offline_e2e_v1/`.
  **11/11 kontrak mock E2E PASS** di Windows
  dan langsung pada Pi: 151 frame nyata,
  151/151 projection autosave in-memory,
  9 negative FAIL_CLOSED, keputusan AI N/A.
  Bukti Pi identik dengan output Windows;
  tidak ada raw edited, firmware flashing,
  Nextion nyata/aktuator atau model diaktifkan.
- **Tahap 8 mock selesai; Tahap 9 fisik dan
  Tahap 10 rilis AI tetap NO-GO**.
  Laporan `docs/reports/2026-10-12_RISET_USB_PI5_DAN_E2E_TAHAP8.md`.
## 12 Oktober 2026 — Catu daya ATmega dan Pi terpisah

- Operator menegaskan USB ATmega↔Pi tetap
  terhubung, sementara ATmega dan Pi masing-
  masing memakai adaptor daya sendiri.
- Menambahkan pemeriksaan G0 terkait
  jenis board/USB FT232R, jalur adaptor
  eksternal, pemilihan VBUS/backfeed,
  catu aktuator/sensor, dan dampak reset.
  Arduino Mega Rev3 mempunyai pemilihan
  sumber otomatis, tetapi tidak boleh
  diasumsikan pada PCB custom.
- **G0 partial/belum PASS, G2/G3 tetap
  tidak dijalankan**. Tidak ada pembukaan
  port serial, flashing, atau pengendalian
  aktuator.

## 12 Oktober 2026 — Klarifikasi USB langsung ATmega → Pi

- Operator menegaskan koneksi **kabel USB langsung
  dari board ATmega ke USB Raspberry Pi**,
  bukan GPIO14/15 atau FT232 TTL kabel eksternal.
  USB FT232R `ttyUSB0` terenumerasi secara
  pasif dan konsisten sebagai bridge USB-serial,
  tetapi pencocokan board dan daya USB
  belum ada bukti fisik.
- Mengonfirmasi UART0/Serial 115200 untuk
  host, Serial2 9600 untuk Nextion,
  Serial1 belum aktif. Membetulkan satu
  dokumen wiring historis TQFP-100
  dari pin kemasan 8/9 yang salah menjadi
  PH0/RXD2 12 dan PH1/TXD2 13.
- Mengarahkan SOP ke jalur USB langsung,
  mempertegas gerbang G0 VBUS/backfeed
  belum PASS, G1 kabel terpasang menurut
  operator, G2/G3 NOT RUN.
  Tidak ada port serial dibuka/flash/
  kontrol aktuator selama pemeriksaan.
- Menambah regresi static contract
  `scripts/test_stage7_usb_contract.py`.
## 12 Oktober 2026 — Konfirmasi jalur FT232 dan G0 safety hold

- Operator menetapkan **FT232 USB-to-TTL**
  (`ttyUSB0`) sebagai jalur Pi–ATmega,
  namun tidak mengetahui USART MCU dan
  belum memverifikasi level tegangan TTL
  sambungan langsung.
- Audit repo tidak menemukan skematik PCB
  yang cukup untuk membuktikan TX/RX,
  ground, VCCIO, atau VBUS/backfeed.
- SOP UART diberi checklist foto, pemeriksaan
  pin dengan daya mati, identitas VCCIO,
  dan izin G2 terpisah. **G0 BLOCKED**;
  tidak membuka serial, menjalankan
  model, atau menggerakkan aktuator.

## 12 Oktober 2026 — Verifikasi topologi UART Pi (tanpa port open)

- Operator menyatakan telah memasang koneksi
  UART ATmega2560 ke Pi. SSH Tailscale
  berhasil setelah autentikasi ulang.
- Audit Pi read-only: FT232R USB-to-TTL
  `ttyUSB0`, GPIO UART0 `ttyAMA0`,
  pinmux GPIO14 TXD0/GPIO15 RXD0,
  `serial0 -> ttyAMA10` debug.
- Source firmware menulis ke `Serial`
  115200, bukan `Serial1` D18/D19;
  pemetaan kabel dan level tegangan
  belum diketahui. **Tidak ada port
  dibuka, flashing atau aktuator yang
  dikendalikan.**
- Menambah skrip dan regresi
  `stage7_uart_preflight.py`,
  `test_stage7_uart_preflight.py`
  serta SOP/report khusus UART.
  Gerbang fisik tetap **NO-GO**
  sampai wiring/voltage dan izin tes
  read-only dikonfirmasi.
## 11 Oktober 2026 — SOP bench USB ATmega → Raspberry Pi

- Membuat `docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`
  dengan G0 pengecekan PCB/sumber daya/VBUS,
  G1 pemasangan kabel, G2 pembacaan serial
  **115200 read-only** dan auto-reset DTR,
  G3 opsional satu siklus pengujian Nextion
  **5 × (25s purging + 5s collecting)**.
- Perintah enumerasi dan pemilik port disusun
  agar **tidak otomatis membuka** tty,
  beserta kriteria PASS/FAIL/INCONCLUSIVE,
  formulir operator, penghentian/rollback
  dan larangan flashing/USB bypass/aktuator
  tanpa izin tambahan.
- `stage7_pi_adapter.py` menerapkan
  POSIX exclusive advisory dan batas panjang
  pembacaan USB; regresi stub PySerial memeriksa
  DTR/RTS nonaktif, batas buffer, dan
  **tidak pernah menulis ke MCU**.
- **SOP PREPARED, hardware NOT RUN**.
  Laporan `docs/reports/2026-10-11_TAHAP7_USB_BENCH_SOP_QA.md`.
## 11 Oktober 2026 — Tahap 7: venv dan replay CSV asli langsung di Pi

- SSH Tailscale ke `enose-v3@enose-pi5` berhasil;
  Raspberry Pi 5 Model B Rev 1.1, Debian 13,
  Python 3.13.5 dan preflight read-only terverifikasi.
- Membuat `~/smart-coffee-stage7/.venv` di Pi
  dan memasang **pyserial==3.5** hanya ke venv;
  tidak mengubah Python global/layanan.
- Menambah `scripts/stage7_pi_adapter.py` (mode
  replay-csv/replay-jsonl dan serial-readonly
  yang dilindungi izin eksplisit), regresi
  `scripts/test_stage7_pi_adapter.py`,
  serta `scripts/requirements-stage7-pi.txt`.
- Mentransfer satu CSV asli dan source + ringkasan
  gate melalui SSH/SCP; hash SHA256 CSV cocok
  antara host dan Pi. Regresi bridge/adapter/
  preflight **PASS di Pi**, replay
  `D-GAW_B33.csv` **151 sampel, COMPLETE_QA,
  AI_TEST=N/A**, tanpa serial fisik.
- Menambah laporan dan bukti
  `docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`
  dan `results/stage7_pi_remote_v1/`.
  ATmega/Nextion/aktuator/COM5 tetap tidak disentuh.

## 10 Oktober 2026 — Tahap 7: adapter Pi dan mock protokol aman

- Berdasarkan konfirmasi operator, ATmega tidak dikoneksikan ke
  COM5 dan Pi 5 sudah dinyalakan untuk remote. Tanpa identitas
  SSH valid, **tidak mengklaim Pi telah diakses**, USB/UART
  fisik belum dapat diuji.
- Memprioritaskan USB Serial 115200 untuk integrasi pertama.
  Serial1 GPIO memerlukan bukti skematik/level shifter
  dan konfigurasi UART Pi 5; debug UART utama default
  berada pada header khusus.
- Menambah `scripts/stage7_bridge.py`: validator
  JSON-per-line legacy, session ID lokal, kontrol urutan
  fase/indeks/uptime, fail-closed disconnect/duplikasi,
  keputusan AI_TEST N/A tanpa model. Envelope v1 dan
  ACK/NACK baru **simulasi**, belum aktif di firmware.
- Menambah `scripts/stage7_pi_preflight.py` read-only
  dan tes `test_stage7_bridge.py`,
  `test_stage7_pi_preflight.py`, replay CSV asli
  `results/stage7_offline_v1/` tanpa mengubah raw.
- SOP `docs/STAGE7_PI_REMOTE_AND_SERIAL_SOP.md` dan
  laporan `docs/reports/2026-10-10_TAHAP7_PI_INTEGRATION_PREP.md`.
  Firmware, HMI, USB/COM5, EEPROM dan aktuator tidak diubah.
- QA regresi Stage 0–7, CSV umum 89/89, kontrak HMI
  12 halaman/23 event, build PlatformIO 2/2 **PASS**.
  Klien SSH Windows tersedia; remote Pi dan serial
  hardware tetap **NOT TESTED**.
## 10 Oktober 2026 — Dataset ilmiah riil dan gerbang Tahap 6

- Meneliti dataset publik kopi E-Nose yang berkaitan
  dengan artikel peer-reviewed, terutama CoffeePow-4,
  Aroma-7, Colombian Coffee (58 pengukuran), dan
  riset sembilan sensor MOS kopi 2023.
- Mengunduh CoffeePow-4/Aroma-7 asli dari Zenodo
  (MD5 publisher dan SHA256 **PASS**), menemukan
  3.583/4.750 rangkaian lengkap, 4 pembacaan tail
  tak lengkap pada Aroma-7, serta overlap data
  CoffeePow-4 secara **identik** di Aroma-7.
- Menambah downloader hash-verified, benchmark
  40 kombinasi (2 dataset × 2 target × 2 split × 5 model),
  tes regresi, dan hasil `results/external_coffee_enose_v1/`.
  RF 4-kelas CoffeePow-4 macro-F1 0,906 random
  vs 0,501 tail; **bukan** skor perangkat lokal.
- Dataset Colombian Mendeley terverifikasi metadata
  tetapi **HTTP 403** saat unduh melalui API; data
  9 MOS paling mirip hardware **on request**.
- Tahap 6 hanya implementasi gerbang fail-closed
  `stage6_release_gate.py` dan regresinya;
  `model_promotion_allowed=false`, AI_TEST N/A.
  Tidak ada model final, flashing, pengubahan
  firmware/Nextion/COM5 atau penggabungan data luar ke lokal.
- Laporan `docs/reports/2026-10-10_RISET_DATASET_EKSTERNAL_DAN_TAHAP6.md`.
## 9 Oktober 2026 — Tahap 5: risiko model, drift sintetik dan unknown

- Mengembangkan `scripts/stage5_validation.py` beserta uji
  `scripts/test_stage5_validation.py`, menggunakan input SHA256
  snapshot Stage2/3 versi terkoreksi dan **83 kandidat kopi**.
- Membandingkan RF82 dan LDA10 pada 4-fold LOBO dengan prediksi
  out-of-fold, risk–coverage a priori, metrik per kelas, dan
  bootstrap empat batch secara deskriptif; **tidak melakukan
  tuning threshold atau menyimpan model akhir**.
- **P0:** kedua model memprediksi *light roast* terhadap **5/5
  sampel udara bersih valid**, 0/5 ditolak pada ambang 0,6.
  Kedua model salah pada 38/83 file kopi OOF. Ketepatan
  confidence dan kemampuan deteksi unknown **tidak tervalidasi**.
- Simulasi pergeseran gain ADC ±5%/±10% memperlihatkan
  RF berubah prediksi pada 8–17 file, sedangkan LDA response10
  tetap dalam asumsi transformasi sintetik (bukan data fisik).
- Keluaran `results/stage5_validation_v1/`, laporan
  `docs/reports/2026-10-09_TAHAP5_GENERALISASI_UNKNOWN_QA.md`.
  Tahap 5 engineering offline selesai tetapi **NO-GO
  validasi prospektif, unknown, dan promosi model**.
- QA regresi Stage 0–5, PlatformIO dua environment, Nextion 12
  halaman/23 event, dan validator struktur 89/89 CSV **PASS**;
  tes tersebut bukan bukti kelayakan inferensi produksi.

## 9 Oktober 2026 — Tahap 4: CAW udara bersih dan benchmark LOBO

- Operator mengonfirmasi **kode CAW dan seluruh batch B37 = udara bersih**.
  Menambahkan empat CAW B33–B35 ke daftar pengecualian yang sebelumnya
  mencakup dua B37. Kode audit/fitur/plot mencegah kebocoran CAW/B37
  ke training dan grafik berlabel kopi, termasuk fail-closed SHA256.
- Menghasilkan snapshot baru `data/analysis/stage2_v2/` (83 kandidat
  kopi + 6 udara bersih, total 89 CSV), `data/processed/stage3_v2/`
  (**83 fitur kandidat valid**), mempertahankan snapshot lama sebagai arsip
  dan **tidak** mengedit raw.
- Menambahkan `scripts/stage4_model_benchmark.py` dan regresi negatif
  `scripts/test_stage4_model_benchmark.py`: 7 grup fitur × 8 baseline/
  challenger × 4 batch LOBO = **224 fit/fold**, 4.648 prediksi.
  Skor deskriptif tertinggi RF expanded82 macro-F1 **0,490**; LDA response10
  **0,482**; penurunan pada B34/B35 masih tinggi.
- Artefak benchmark `results/stage4_lobo_v2/` meliputi metrik fold,
  metrik per kelas, confusion matrix, prediksi terindeks SHA256, peringkat
  eksploratori serta config versi sklearn. Tidak ada model disimpan atau
  di-deploy. Laporan `docs/reports/2026-10-09_TAHAP4_MODEL_LOBO_CAW_CORRECTION.md`.

## 9 Oktober 2026 — Tahap 3: kontrak fitur MQ3 deterministik

- Menjadikan `extract_sensor_features` fungsi ekstraksi murni untuk input frame sensor tanpa label; kontrak legacy 62 fitur dipertahankan. Tambah varian eksploratori 82 fitur, dengan tujuh grup subset yang didefinisikan tanpa fitting/model.
- Memeriksa 87 kandidat Stage 2 berdasarkan SHA256. **86 lolos ekstraksi ketat**, `L-CAW_B34.csv` ditahan (sampel purging indeks 8 siklus 1 hilang). Data raw tidak diubah; dua file bench B37 dikecualikan.
- Tambah `scripts/stage3_feature_pipeline.py`, `scripts/test_stage3_feature_pipeline.py`, `data/processed/stage3_v1/`, dan kontrak `data/processed/STAGE3_FEATURE_CONTRACT.md`. Melindungi dari file/hash berbeda, metadata/label bocor ke model, CSV ADC invalid, suhu/kelembapan hilang, penulisan ke raw atau overwrite output tidak sengaja.
- Dokumentasi: `docs/reports/2026-10-09_TAHAP3_PREPROCESSING_FEATURE_QA.md`. Model belum dilatih; label/spesimen independen, baseline dan evaluasi LOBO masih membutuhkan Tahap 2/4/5.
- QA akhir **PASS**: PlatformIO kedua environment, HMI 12 halaman/23 event, validator 89/89 CSV umum, 87/87 B32–B35 canonical, regresi Stage 0–3, parity/tes negatif dan compileall. **Satu file Stage 3 tetap HOLD** bukan kegagalan yang disembunyikan.

## 9 Oktober 2026 — Tahap 2: provenance dan kualitas data

**Status:** perangkat audit snapshot dan QA reproduksibel selesai; verifikasi label/origin serta identitas spesimen tetap P0 terbuka.

- Catat konfirmasi operator bahwa valve/pompa berpindah mengikuti 25/5 detik dan Nextion mencapai halaman selesai tanpa error (bukti observasi, belum pengukuran instrumen). Uji negatif Tahap 1 tetap terbuka.
- Tambahkan skrip `stage2_dataset_audit.py` beserta tes negatif untuk manifest SHA256, kualitas CSV, label dan cohort, kelengkapan kelas, perubahan baseline purge, proxy drift, serta flag outlier eksploratori.
- Audit **89 CSV B32+**: 87 kandidat belum disetujui untuk ML dari B32–B35 dan 2 file udara bersih B37 dikecualikan. Terdapat 9 sel kode–batch kosong, 4 sel berulang dan 33 flag file–kanal untuk review (bukan 33 file rusak).
- Perkuat generator plot agar mengabaikan bench B37 berdasarkan hash serta menahan batch baru B36+ sampai provenance direview; data mentah dan grafik eksisting tidak dihapus.
- Buat keluaran `data/analysis/stage2/` dan laporan `docs/reports/2026-10-09_TAHAP2_PROVENANCE_KUALITAS_DATASET.md`. Tidak dilakukan training model atau operasi alat.

## 9 Oktober 2026 — Hasil bench Nextion B37 dengan udara bersih

- Operator menyampaikan selang menggunakan udara bersih selama batch B37; dua file final `L-MING_B37.csv` dan `M-MING_B37.csv` ditemukan dari log listener COM5.
- Validator canonical untuk **150 dan 152 baris** sama-sama PASS. Evaluasi target ketat 25/5×5 PASS untuk L-MING, dan FAIL untuk M-MING karena ada 6 collecting pada siklus 1 dan 5; indeks tetap kontigu.
- Mencatat checksum serta hasil SOP B01–B08 pada `docs/reports/2026-10-09_TAHAP1_BENCH_B37_UDARA_BERSIH.md`. Tidak ada aksi serial atau modifikasi hardware oleh agen.
- Menambahkan `data/analysis/bench_only_exclusions.csv` dan peringatan di `data/raw/README.md`: label kopi dalam kedua file B37 **tidak valid sebagai ground truth**, kecualikan dari training/evaluasi roast/origin. File mentah tetap utuh.
- Memperbaiki laporan QA bench agar kasus ekstra sampel tidak disalahartikan sebagai sample_idx nonkontigu, dan membedakan validator CSV umum dengan target bench ketat.

## 9 Oktober 2026 — Preflight bench pasif Tahap 1

**Status:** satu sesi serial USB→listener→CSV final **PASS** berdasarkan bukti read-only, belum menjadi verifikasi aktuator/Nextion/perangkat menyeluruh.

- Memeriksa status listener aktif COM5@115200 dan log START/COMPLETE tanpa membuka COM5 maupun mengganggu proses.
- Memvalidasi `L-MING_B32_20261009_172056.csv`: 150 baris sensor, lima siklus × 25 purging + 5 collecting, timestamp MCU 996–1004 ms antar-sampel, kanal numerik lengkap, suhu/kelembapan terbaca. File mentah **tidak** diubah/di-commit.
- Menambah `scripts/bench_stage1_passive_qa.py` (validator CSV final non-destruktif) dan `scripts/test_bench_stage1_passive_qa.py` (fixture positif/negatif).
- Membuat **draf** `docs/SOP_BENCH_TAHAP1.md` dan bukti `docs/reports/2026-10-09_TAHAP1_BENCH_PASIF_PRECHECK.md`.
- Remaining gate: operator mengesahkan scope dan keselamatan SOP aktif, periksa firmware terpasang, uji valve/Nextion/fault cases pada perangkat fisik. **Tidak ada flashing atau penghentian listener.**

## 9 Oktober 2026 — Tahap 1: pengamanan firmware dan akuisisi (offline)

**Status:** peningkatan firmware/QA offline diterapkan; tahap verifikasi timing dan hardware fisik **BELUM SELESAI**.

- `#pin_scan;` kini selalu ditolak dengan `PIN_SCAN_DISABLED`, tanpa mengubah pin GPIO/I2C/UART; implementasi pemindaian lama dibuang.
- Uji valve manual melalui serial dinonaktifkan secara default lewat `ENABLE_MANUAL_ACTUATOR_TESTS=0`; hanya dapat diaktifkan melalui build khusus ber-SOP.
- Perintah serial `#start;` menolak ADC yang belum lengkap; `#scan;` menolak pemindaian I2C selama akuisisi aktif.
- Event `ACQ_START` pada `ai_test` tidak lagi memuat label roast/origin/batch atau filename. Metadata untuk `labeled_data` tetap kompatibel.
- `adsCallback` mengirim data sesuai fase saat dibaca terlebih dahulu, baru memproses transisi/COMPLETE; tidak lagi mengirim frame sensor saat idle/paused. Ini mencegah event COMPLETE menutup CSV sebelum sampel terakhir dikirim pada callback yang sama.
- Menambah `scripts/test_stage1_firmware_contract.py` dan kasus tambahan `scripts/test_acquisition_integrity.py` (AI_TEST tanpa label, completion duplikat, STOP parsial).
- Bukti, mitigasi dan pekerjaan bench: `docs/reports/2026-10-09_TAHAP1_FIRMWARE_AKUISISI_QA.md`. Tidak ada flashing, akses COM5, perubahan EEPROM, atau uji aktuator fisik.

## 9 Oktober 2026 — Tahap 0: audit kontrak sistem dan revisi baseline

**Status:** audit offline dan dokumentasi **selesai**; verifikasi fisik, keputusan label, serta transport Pi masih menjadi pekerjaan tahap berikutnya.

- Menambahkan `docs/02_KONTRAK_SISTEM_DAN_KEPUTUSAN_TAHAP0.md`: matriks sumber acuan, batas bukti, pemetaan UART/USB, definisi dataset, dan daftar tindak lanjut T0-01–T0-07.
- Mengoreksi kekeliruan dokumentasi tentang pin TQFP-100 Nextion berdasarkan datasheet Microchip: PH0/RXD2 = pin 12 dan PH1/TXD2 = pin 13 (header Arduino D17/D16 tetap).
- Memperbaiki komentar durasi akuisisi firmware yang usang (180/60 detik → 25/5 detik, 5 siklus), keterangan diagnostik pin D19/RX1, dan label I2C hardware tanpa mengubah logika kontrol aktuator.
- Menambahkan `scripts/test_stage0_contract.py` untuk pemeriksaan otomatis lintas firmware, JSON, CSV, urutan ADC, alamat ADS1115, pin Nextion, HMI dan konsistensi metadata preset.
- Menyelaraskan current state, roadmap, arsitektur Pi, README, panduan Nextion, AGENTS.md, dan audit QA/QC. Transport Pi saat ini USB Serial; UART terpisah masih rancangan.
- Pengujian: **PASS** build PlatformIO dua environment, pemeriksaan HMI, regresi akuisisi/fitur, 86/86 CSV B32–B35, 18/18 B32, tes kontrak Tahap 0, sintaks Python, dan Git diff check.
- Risiko tersisa: `#pin_scan` menyentuh D19/RX1 dan D20/SDA; label UI masih masuk ke event `AI_TEST`; kode origin TEM/MUK/CAW dan tiga preset tambahan perlu konfirmasi; wiring fisik serta inferensi Pi belum diuji.

**Bukti dan langkah berikutnya:** `docs/reports/2026-10-09_TAHAP0_AUDIT_KONTRAK_DAN_QA.md`, `docs/01_MASTER_E2E_ROADMAP.md`. Commit milestone dapat dilacak melalui Git pada branch `wahyu`.
