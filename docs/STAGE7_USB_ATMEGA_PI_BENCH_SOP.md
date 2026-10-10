# SOP Bench Tahap 7 — USB ATmega2560 ↔ Raspberry Pi 5 (115200 baud)

**Versi:** v1.0 · 11 Oktober 2026

**Status:** SIAP DIREVIEW OPERATOR — **BELUM DIEKSEKUSI SECARA FISIK**
**Sasaran:** hanya memverifikasi enumerasi USB dan penerimaan *serial read-only*,
diikuti satu sesi akuisisi Nextion **hanya jika diberi izin khusus terpisah**.
Ini bukan SOP kalibrasi, firmware upload, model AI, ataupun uji E2E penuh.

## 0. Kontrak dan kondisi awal yang sudah terverifikasi

| Parameter | Kontrak/bukti |
|---|---|
| Host | Raspberry Pi 5 Model B Rev 1.1, Debian 13, Python 3.13.5 |
| Remote | Tailscale SSH `enose-v3@enose-pi5`, sudah **PASS** |
| Software Pi | `/home/enose-v3/smart-coffee-stage7/.venv`, `pyserial==3.5` |
| Link kandidat | USB ATmega → USB Pi, firmware `Serial` **115200, 8N1** |
| Nextion | `Serial2` **9600**, jalur terpisah; tidak disentuh |
| Akuisisi | 5 siklus × 25 detik purging + 5 detik collecting, nominal sekitar 150 frame |
| Penanggung jawab aktuator | Firmware ATmega, **bukan** software di Pi |
| Model AI | Tahap 6 **NO-GO**, keluaran `AI_TEST=N/A` |
| Status awal yang diketahui | ATmega **belum disambungkan** ke USB Pi; port ttyACM/ttyUSB belum ditemukan |
| Bukti software | Replay CSV nyata `D-GAW_B33.csv`: 151 frame, `COMPLETE_QA` dalam toleransi, tanpa hardware link |

**Referensi teknis:**
- Arduino Mega 2560 Rev3, bagian *Automatic (Software) Reset*:
  https://store.arduino.cc/products/arduino-mega-2560-rev3
- PySerial API (DTR/RTS dapat berubah saat membuka port):
  https://pyserial.readthedocs.io/en/latest/pyserial_api.html
- `docs/STAGE7_PI_REMOTE_AND_SERIAL_SOP.md`
- `docs/reports/2026-10-11_TAHAP7_PI_VENV_OFFLINE_REPLAY.md`

**Peringatan reset:** pada desain Arduino Mega standar, transisi DTR
saat USB serial dibuka bisa me-reset MCU. **PCB/perangkat ATmega custom
belum diverifikasi memiliki atau tidak memiliki jalur reset yang sama.**
`dtr=False`, `rts=False`, dan `exclusive=True` pada adapter adalah
mitigasi software, **BUKAN jaminan tidak terjadi reset**. Membuka port
serial adalah tindakan hardware yang memerlukan izin dan pengawasan.
Kabel USB dapat sekaligus membawa **5 V** ke rangkaian; jangan berasumsi
aman pada PCB yang juga memakai PSU eksternal.

## 1. Gerbang persetujuan (wajib berurutan)

**G0 — Review fisik dan daya oleh operator yang hadir di lokasi.**
Pastikan jenis board/antarmuka USB-serial (Mega asli, CH340/FTDI,
atau PCB custom), sumber 5 V, isolasi jalur VBUS, dan ground
berdasarkan skematik. Pastikan **tidak ada potensi backfeed,
arus motor/pompa/valve mengambil daya dari port USB Pi, atau
konflik dengan PSU eksternal**. Jika skema daya tidak diketahui,
**STOP — jangan hubungkan kabel**.

**G1 — Izin memasang kabel USB data.** Setelah G0 lolos,
operator fisik menyiapkan catu daya aman, mengamankan
selang/alat, memastikan sistem **IDLE**, lalu memasang USB
data Pi ↔ ATmega sekali di bawah pengawasan. Langkah ini
**hanya enumerasi**, tidak membuka port serial.

**G2 — Izin membuka port serial read-only.** Hanya setelah port
USB teridentifikasi, tidak sedang dimiliki proses lain, kondisi
aktuator aman, dan risiko reset DTR dinyatakan dapat diterima
operator. Ini **izin terpisah dari G1**.

**G3 — Izin akuisisi satu sesi 5 siklus via Nextion.** Memerlukan
persetujuan tambahan karena tombol Nextion **dapat menggerakkan
pompa dan valve** selama ±150 detik. Jika tidak diberikan,
hentikan pada pemeriksaan pasif G2; jangan menekan Start Test
atau Ambil Data untuk memperoleh frame.

**Pekerjaan saat dokumen ini ditulis: G0/G1/G2/G3 BELUM DISETUJUI
UNTUK EKSEKUSI. Pembuatan dokumen tidak memberi otorisasi
otomatis untuk pemasangan kabel atau pembukaan port.**

## 2. Perlengkapan dan kondisi aman

- Operator **harus ada secara fisik** dekat alat dan memiliki
  akses memutus catu daya/stop darurat jika ada kegagalan;
  operator remote saja tidak cukup.
- Kabel USB **data**, jenis konektor sesuai antarmuka board,
  diketahui layak dan tidak mengalami kerusakan.
- Pi mendapatkan catu daya yang stabil dari PSU yang benar.
  Sensor gas/heater, pompa, valve dan Nextion memiliki skema daya
  yang telah dinyatakan aman terhadap USB host.
- Sistem dimulai **IDLE**, tidak ada akuisisi aktif,
  kalibrasi/EEPROM, firmware upload, atau program lain
  yang memakai UART/port USB yang sama.
- Hindari dua host sekaligus mengakses jalur UART0
  (contohnya Windows Serial Monitor/COM5 dan Pi).
  Tidak menjalankan `pio device monitor`, `screen`,
  `minicom`, `picocom` atau `serial.tools.miniterm`
  secara paralel dengan adapter.
- Pada Tahap 7 ini **tidak memakai UART GPIO**,
  tidak menyambungkan pin RX/TX 5 V ke GPIO Pi 3,3 V,
  tidak mengganti firmware/HMI.

## 3. Fase A — pemeriksaan Pi sebelum menghubungkan kabel (G0)

Dari PC Windows (SSH sudah terbukti berhasil):

```powershell
ssh -o StrictHostKeyChecking=yes -o BatchMode=yes enose-v3@enose-pi5
```

Di terminal Pi, perintah **tidak membuka serial dan tidak mengubah OS**:

```bash
cd ~/smart-coffee-stage7
.venv/bin/python scripts/test_stage7_pi_adapter.py
.venv/bin/python scripts/test_stage7_bridge.py
.venv/bin/python scripts/stage7_pi_preflight.py
vcgencmd get_throttled
vcgencmd measure_temp
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
id -nG
systemctl is-active ModemManager 2>/dev/null || true
```

Rekam hasil awal perangkat, daftar port sebelum G1, suhu,
`get_throttled`, nama operator, sumber daya, versi firmware,
dan status Nextion/pompa/valve. `get_throttled=0x0`
ideal pada pemeriksaan ini; jika terjadi masalah
undervoltage, periksa PSU dan **STOP**.
Jika `ModemManager` aktif, periksa apakah ia
akan membuka device otomatis; **jangan** menonaktifkan
layanan tanpa izin tersendiri.

## 4. Fase B — enumerasi setelah operator mengizinkan kabel (G1)

1. Operator lokal memastikan aliran, selang, aktuator dan PSU
   dalam kondisi aman. Pasang USB **sekali** hanya setelah
   G0 dan G1 ditandatangani.
2. Operator amati boot/halaman Nextion serta pompa/valve
   selama dan sesudah pemasangan. **Jika reboot/reset tak
   terencana memicu aktuator atau perilaku tidak aman,
   STOP dan isolasi catu sesuai prosedur alat.**
3. Dari SSH Pi jalankan **enumerasi read-only**:

```bash
lsusb
ls -l /dev/serial/by-id/ 2>/dev/null || true
ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true
.venv/bin/python scripts/stage7_pi_preflight.py
```

4. Pilih device hanya jika **perbedaan sebelum–sesudah
   koneksi** dan identitas USB (VID/PID/serial) menunjukkan
   board yang benar. Preferensikan path stabil
   `/dev/serial/by-id/...` jika tersedia; jika tidak
   ada, path `/dev/ttyACM0` atau `/dev/ttyUSB0`
   hanya contoh, **jangan langsung dipakai tanpa verifikasi**.
5. Jalankan pemeriksaan kepemilikan **tanpa membuka port**.
   Ganti `<PORT_TERVERIFIKASI>` dengan path yang benar:

```bash
PORT='<PORT_TERVERIFIKASI>'
readlink -f "$PORT"
ls -l "$PORT"
fuser "$(readlink -f "$PORT")" 2>/dev/null || true
udevadm info --query=property --name="$PORT" 2>/dev/null | grep -E '^(ID_VENDOR|ID_MODEL|ID_SERIAL|ID_PATH)=' || true
```

Jika ada proses lain menggunakan port, port tidak jelas,
permission ditolak, atau daya berisiko: **STOP**. Jangan
`sudo chmod 666`, `usermod`, kill proses lain,
restart layanan, atau menjalankan flash sebagai jalan pintas.
Jika `fuser` tidak tersedia atau tidak dapat memeriksa
kepemilikan, **jangan menganggap port bebas**;
lengkapi pemeriksaan melalui operator/administrator.

**PASS Fase B** hanya berarti *USB dikenali dan tidak
ada indikasi kondisi fisik berbahaya*. **Belum berarti
payload UART/baud benar atau reset-free.**

## 5. Fase C — read-only serial yang diizinkan (G2)

**HANYA SETELAH operator G2 setuju dan berada di dekat alat.**
Pembukaan port bisa memicu **auto-reset walau program tidak
menulis bytes**. Jika board reboot, catat waktunya dan
observasi keamanan; bila tidak stabil, hentikan.

Gunakan terminal Pi yang sama (satu pemilik port), pilih path
yang benar dari Fase B dan nama output **baru**:

```bash
cd ~/smart-coffee-stage7
PORT='<PORT_TERVERIFIKASI>'
.venv/bin/python scripts/stage7_pi_adapter.py serial-readonly \
  --port "$PORT" --baud 115200 --duration 20 \
  --acknowledgment I_APPROVE_USB_SERIAL_READONLY \
  --output results/pi_stage7/usb_bench_G2_run01.json
```

Catatan: baris perintah di atas adalah **contoh untuk
digunakan setelah izin G2**; penulisan dokumen ini
bukan perintah untuk mengeksekusinya sekarang.
Program membuka **port USB serial eksklusif**, mengatur
DTR/RTS False, membaca frame sampai newline dengan batas
panjang, dan **tidak memanggil `write()` atau mengirim
perintah apa pun**. Port ditutup setelah sesi atau timeout.
Flag `--duration` dibatasi maksimal 180 detik;
sesi pasif G2 sengaja dibatasi **20 detik**.

**Tanpa G3**, karena MCU saat IDLE bisa tidak mengirim
frame sensor periodik, hasil `NOT_STARTED` / `N/A`
atau exit code 2 **tidak otomatis berarti link rusak**;
itu hanya berarti sesi penuh tidak terlihat. Catat
log boot/diagnostik yang terlihat pada Nextion bila ada,
perubahan reset, serta status port. Jangan mengirim
`#start;`, `#scan;`, `#status;`, `#pin_scan;`,
atau `#valve_*` dari Pi pada SOP ini.

Jika ingin berhenti lebih awal, operator boleh
`Ctrl+C`. Program yang terinterupsi mungkin belum
menulis file JSON ringkasan; laporkan **ABORTED**
di checklist manual, jangan mengklaim PASS dari
ketiadaan error.

## 6. Fase D — satu uji akuisisi melalui Nextion (G3, opsional)

Langkah ini **bukan** bagian wajib pemeriksaan koneksi
pasif dan memerlukan persetujuan G3 khusus.

1. Siapkan sistem/selang pada **udara bersih**,
   lakukan pemeriksaan keamanan sensor, pompa,
   valve, ventilasi dan catu daya bersama operator.
2. Pastikan Fase B PASS, G2 PASS terhadap keselamatan
   pembukaan port, software mendengar pada 115200,
   tidak ada proses lain membuka port, dan operator
   mengawasi Nextion secara fisik.
3. Jalankan satu kali `serial-readonly` **sebelum
   memulai akuisisi** menggunakan file keluaran
   baru (bukan file G2):

```bash
cd ~/smart-coffee-stage7
PORT='<PORT_TERVERIFIKASI>'
.venv/bin/python scripts/stage7_pi_adapter.py serial-readonly \
  --port "$PORT" --baud 115200 --duration 180 \
  --acknowledgment I_APPROVE_USB_SERIAL_READONLY \
  --output results/pi_stage7/usb_bench_G3_run01.json
```

   Operator tekan Start pada Nextion **hanya setelah
   penerima sudah siap**, idealnya dalam 10 detik.
   Maksimal **satu sesi lima siklus**; 180 detik
   mencakup ±150 detik akuisisi dan margin.
4. Operator catat apakah purging/collecting benar-benar
   berlangsung **25/5 detik**, total sekitar **150 detik**,
   Nextion sampai halaman selesai, tidak ada alarm,
   pompa/valve sesuai SOP fisik dan tidak terjadi
   reset/putus daya di tengah sesi.
5. Periksa ringkasan JSON di Pi tanpa menulis data ke MCU:

```bash
.venv/bin/python -m json.tool results/pi_stage7/usb_bench_G3_run01.json
```

**Kriteria QA data untuk sesi yang selesai:**

| Komponen | Kriteria |
|---|---|
| Data serial | 115200 8N1, JSON-per-line yang dikenali |
| Start / finish | `ACQ_START` dan satu `ACQ_COMPLETE` yang konsisten |
| Siklus | 1–5 berurutan, purging → collecting tiap siklus |
| Sample index | Bertambah dari 1 setiap fase, tanpa gap atau duplikasi |
| Timestamp | MCU uptime naik monoton selama sesi |
| Jumlah frame | Nominal 150; validator saat ini toleransi purging **24–26** dan collecting **4–7** per siklus |
| Keputusan aplikasi | `final.quality=COMPLETE_QA`; `final.status=N/A`, model tidak dipanggil |
| Keselamatan | Aktuator mengikuti state MCU; Pi mengirim **0** perintah dan tidak mengubah HMI |
| Waktu/reset | Tidak ada putus koneksi/reset berbahaya saat akuisisi; jika ada, STOP/FAIL |

**Penting:** lulus toleransi `COMPLETE_QA` dengan 151/152
frame tetap harus ditandai **VARIANCE** dan dijelaskan;
tidak boleh diklaim sebagai persis 150 frame atau
kesempurnaan timing fisik.

## 7. Matriks hasil, penghentian dan rollback

| Situasi | Penanganan / keputusan |
|---|---|
| USB tak muncul di enumerasi | Cek kabel data, PSU, konektor dan interface dengan operator; **STOP**, jangan memaksa port fiktif |
| Identitas device tak jelas / ada dua owner | **STOP**, audit `fuser`/udev; jangan matikan proses otomatis |
| Muncul reboot akibat USB/DTR | Catat bukti dan efek ke aktuator; STOP bila tak aman; ulang hanya setelah mitigasi |
| `Permission denied` membuka device | **BLOCKED**, cek grup device dan kebijakan akses; tanpa `sudo chmod` spontan |
| Tidak ada frame ketika IDLE | **INCONCLUSIVE**, bukan PASS maupun FAIL transport |
| JSON rusak, sample_idx gap, fase mundur | **FAIL_CLOSED**, simpan hasil; jangan lanjut pengujian aktif |
| Session selesai tapi `N/A` | **Benar** untuk AI pada Tahap 6 NO-GO; bukan masalah serial |
| Nextion hang / valve/pompa tidak sesuai | **STOP segera oleh operator**, pulihkan catu/alat sesuai SOP lokal |
| SSH terputus | Tidak melakukan *auto-reconnect* pembukaan serial atau restart aktuator. Operator lokal wajib mengawasi dan menghentikan pengujian dengan aman; catat sesi sebagai **INCONCLUSIVE** |
| Output JSON sudah ada | Program menolak overwrite; buat nama baru, jangan hapus hasil sebelumnya |

**Urutan penghentian:** operator pastikan state fisik
aman; hentikan pembacaan host bila perlu (`Ctrl+C`);
cek proses adapter tidak berjalan; tutup kepemilikan port;
baru lepaskan kabel USB jika kondisi PSU/perangkat aman
dan sesuai rekomendasi penanggung jawab hardware.
Jangan menghapus evidence, reset firmware, atau
menjalankan kalibrasi sebagai pemulihan otomatis.

## 8. Formulir bukti bench (isi hanya setelah pengujian benar-benar dilakukan)

| Item bukti | Isian operator |
|---|---|
| Tanggal / jam WIB | ... |
| Operator lokal / pengawas | ... |
| Board/PCB revision dan jenis USB bridge | ... |
| Sumber daya ATmega, Pi, sensor, pompa, valve | ... |
| Status daya, VBUS/backfeed dan skematik (G0) | PASS / FAIL / BELUM |
| Izin G1 kabel USB | Disetujui / Tidak |
| Port Linux + ID_VENDOR/ID_MODEL/ID_SERIAL | ... |
| Status pemilik port `fuser` | ... |
| Observasi boot/reset setelah koneksi | ... |
| Izin G2 buka port dan risiko DTR | Disetujui / Tidak |
| Nama file bukti G2 / SHA256 | ... |
| Izin G3 menjalankan 5 siklus | Disetujui / Tidak |
| Sampel dan durasi tiap fase | ... |
| Observasi Nextion, pompa, valve | ... |
| Nama file bukti G3 / SHA256 | ... |
| Hasil per fase | PASS / VARIANCE / FAIL / NOT RUN |
| Keputusan keseluruhan | PASS / INCONCLUSIVE / FAIL / NOT RUN |
| Temuan risiko dan aksi korektif | ... |
| Persetujuan/ttd operator | ... |

**Status saat pembuatan SOP: seluruh G0–G3 dan uji
hardware bertanda NOT RUN.** Keberhasilan emulator,
replay CSV historis, SSH dan firmware build
**tidak** membuktikan serial fisik.
