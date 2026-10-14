# Audit ulang final software — enam menu Nextion, G3, dan tampilan AI (RC2)

**Tanggal:** 14 Oktober 2026 WIB. **Lingkup:** source ATmega2560, HMI Nextion,
adapter read-only Raspberry Pi, kontrak data, serta regresi offline.
**Baseline:** RC1 `63d9477`; hasil G3 fisik 14 Oktober setelah reboot.
**PENTING:** hasil audit dan perbaikan RC2 di source **belum** di-flash ke
PCB, sehingga tidak boleh disebut firmware running/production verified.

## Interpretasi bukti fisik

Operator melihat seluruh lima siklus selesai pada LCD dan layar
`Test Complete – AI Result`. Operator menegaskan nilai Roast Level,
Coffee Origin, dan Roast Probability semuanya **`N/A`**.
Ini **sesuai release gate AI** (`USE_ON_DEVICE_INFERENCE=0`), bukan
bukti inferensi rusak. Secara independen, listener Pi saat G3 lama
mendeteksi 1 `EVT:AI_START`, 1 `EVT:TEST_START`, 1 `ACQ_START`,
6 `PHASE_CHANGE`, 99 frame sensor valid, serta 80 sensor berfase
`idle`; `FW_HELLO` tidak teramati. `ACQ_START` mode ai_test
ditolak karena label leakage dari firmware terpasang yang
belum sesuai source RC1. **Tidak ada `ACQ_COMPLETE` tervalidasi
oleh Pi**, meski operator menyaksikan selesai pada HMI.
Tidak ada klaim G3 PASS atau model AI sudah siap.

## Audit keenam menu utama

| Tombol `pHome` | HMI event | Firmware (source RC2) | Safeguard |
|---|---|---|---|
| Start Test | `EVT:TEST_START` | Masuk `pTest`; tombol kedua `EVT:AI_START` mulai `ai_test` | Sensor 10/10 dan IDLE; label ground truth tidak disertakan |
| Take Data | `EVT:TAKE_OPEN` | Masuk `pTake`, memilih roast/origin/batch; `EVT:DATA_START` akuisisi `labeled_data` | Tidak mencampur data dengan AI_TEST, CSV harus valid |
| Settings | `EVT:SETTINGS` | Masuk `pSettings` | Tidak boleh berpindah saat akuisisi aktif |
| History | `EVT:HISTORY` | Masuk `pHistory`; ekspor via tombol khusus | Tidak boleh berpindah saat akuisisi aktif; daftar lokal belum database permanen |
| Calibrate | `EVT:CAL_START` | Tekan di Home hanya buka `pCal`; tombol kedua di `pCal` memulai kalibrasi | ADC siap dan sistem IDLE; prosedur fisik terawasi tetap wajib |
| Exit | `EVT:EXIT` | Menghentikan akuisisi, memberi pesan bahwa power-off manual | Bukan perintah memutus daya/mereset Pi |

**Tidak mengubah gambar, layout, warna, navigasi visual, maupun file HMI.**
Uji memeriksa event `pHome.txt`, event yang terkandung dalam binary
HMI acuan, dan setiap handler firmware. HMI 12 halaman/23 event
lulus pemeriksaan static; bukan touchscreen/touch calibration nyata.

## Perbaikan source RC2

1. **Identitas firmware per sesi**: `SMART_COFFEE_BUILD_ID=g3-rc2-20261014`
   ditambahkan ke `FW_HELLO` dan `ACQ_START.fw_build_id` untuk semua mode.
   Jika pesan boot tidak tertangkap akibat USB/DTR, host masih bisa
   memeriksa marker saat START. Ini *self-reported build/protocol marker*,
   **bukan** signature chip, checksum image terpasang, atau flash read-back.
2. **Fail-closed G3**: adapter tidak lagi menganggap data lima siklus
   yang lengkap sebagai kelulusan hardware bila marker build tidak
   cocok, `ACQ_START` ditolak, atau `ACQ_COMPLETE` tidak diterima tepat
   sekali. Status QA fisik eksplisit `physical_g3_complete_verified`.
   Firmware lama dengan AI label leakage tetap ditolak, tidak ada
   pelonggaran validator, dan nilai sensor/label asing tidak direkam.
3. **Waktu & sinkronisasi operator**: durasi maksimum/default listener
   240 detik (5 siklus nominal 150 detik + waktu persiapan). Sesudah
   port benar-benar dibuka, output `G3_LISTENER_READY_USB_RX_ONLY`
   menjadi penanda aman untuk instruksi tekan tombol; satu sesi saja,
   tidak ada TX dan aktuasi dari adapter.
4. **Navigasi selama akuisisi**: menu `Take Data`, `Start Test`,
   `History`, `Settings`, `Calibrate` ditolak ketika tidak IDLE.
   Firmware mengeluarkan `UI_NAV_BUSY_REJECTED`, tetap di halaman
   terkait agar operator tidak kehilangan kontrol Pause/Cancel.
5. **Kejujuran status AI di LCD**: `LOCAL READY` dan `LOCAL INFERENCE`
   diganti menjadi `AI N/A` dan `AI NOT VALIDATED`; progress AI
   yang belum ada tetap 0, confidence/origin tetap `N/A`, history
   lokal mengidentifikasi AI N/A, dan Settings menampilkan `G3-RC2`
   *hanya ketika source RC2 benar-benar di-flash*.

## QA independen dan regresi

- `scripts/test_home_menu_g3_rc2.py`: uji enam tombol, guard navigasi,
  pemisahan masuk halaman kalibrasi vs eksekusi kalibrasi, output AI
  tidak palsu, fingerprint source, serta replay stream CSV 151 sampel.
  Kasus negatif: label leakage, build asing, sampel hilang semuanya
  gagal tertutup; tidak ada nilai kopi sensitif disalin ke laporan.
- `scripts/test_stage7_pi_adapter.py`: tambahan uji 5 siklus lengkap
  dengan startup FW_HELLO tidak tertangkap tetapi ACQ_START cocok,
  build asing, boot bertentangan, dan validasi ketat.
- `test_preonsite_p0_freeze.py` tetap meloloskan enam safeguard RC1.
- Suite Stage0/1/2/3/4/5/6/7/8/9 offline; validator B32+:
  **88 valid / 1 known-invalid clean air excluded / 0 unexpected FAIL**.
- `pio run -e mega2560 -e nextion_test`: dua build **SUCCESS**, tanpa
  upload. RAM firmware Mega ~45%, Flash ~13,8%.
- Verifikasi Nextion 12 halaman, 23 event, Serial2 9600: **PASS**;
  `python -m compileall -q scripts`, `git diff --check`: **PASS**.
- Tes Pi **PASS** setelah staging adapter RC2: `test_stage7_pi_adapter`,
  `test_stage7_bridge`, `test_stage8_transport_integration`,
  `test_stage8_offline_e2e`, dan compileall. Adapter RC1 disalin sebagai
  `scripts/stage7_pi_adapter.rc1_backup_20261014.py`; test RC1
  sebagai `scripts/test_stage7_pi_adapter.rc1_backup_20261014.py`
  sebelum update. Berkas `.py` RC2 di Pi cocok SHA256 manifest;
  tidak ada port tty yang dibuka dan tidak ada proses akuisisi aktif.
  Pi tetap mendeteksi FT232R `0403:6001`, `throttled=0x0`.

## Gate setelah software freeze RC2

- **Software RC2:** source + build offline + regresi **PASS**.
- **ATmega2560 custom PCB:** chip marking operator teramati tetapi
  signature MCU aktual dan isi flash belum dibaca/di-verify.
- **USB Pi:** reboot 16:33 WIB memulihkan FT232R, G2 10s menerima
  3744 byte; xHCI pernah mati saat serial open sehingga stabilitas
  hardware jangka panjang belum lulus.
- **G3 fisik dengan RC2:** **NOT RUN / REQUIRES SUPERVISION**.
- **AI:** **NO_GO, hasil N/A**; jangan mengarang roast, origin,
  confidence, atau mengklaim 0% sebagai probabilitas terkalibrasi.

**Sebelum pengujian G3 ulang:** operator hardware menyetujui SOP
flashing custom PCB yang benar, tersedia rencana backup/rollback,
identitas chip/board/port upload dipastikan, lalu firmware RC2
dipasang dan diverifikasi. Pisahkan izin flashing dari izin pengujian
pompa/valve. Jangan menggunakan COM5 yang masih merupakan konfigurasi
lokal pengguna untuk mencoba upload ke board yang tersambung ke Pi.
Pastikan FT232R sehat sebelum tiap serial open. Setelah listener
menampilkan `G3_LISTENER_READY_USB_RX_ONLY`, operator menekan START
satu kali, mengamati 5 siklus, dan menerima hasil QA `ACQ_COMPLETE`
beserta marker firmware sebelum menyebut G3 lulus.
