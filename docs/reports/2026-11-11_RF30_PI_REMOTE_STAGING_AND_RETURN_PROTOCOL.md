# RF500 30 Siklus — Remote Pi Preflight, Model Staging, dan Protokol Balik Nextion

**Tanggal:** 11 November 2026, WIB. **Branch:** `wahyu`.
**Status:** SSH + Pi model inference offline + firmware compile-only **PASS**;
hardware serial / flashed firmware / Nextion display **NOT RUN**.

## 1. Akses yang terverifikasi pada Raspberry Pi 5

- Target SSH Tailscale: `enose-v3@enose-pi5`, host key dikenal dan
  `StrictHostKeyChecking=yes`; koneksi SSH read-only berhasil.
  IP Tailscale dan identitas pribadi operator tidak disimpan dalam Git.
- Raspberry Pi 5 Model B Rev 1.1, aarch64, Python 3.13.5.
- FTDI FT232R `0403:6001`, **serial `A10KNJBL`**, terdeteksi sebagai
  `/dev/ttyUSB0` melalui
  `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0`.
  **Identitas ini BERBEDA dari FT232 `A10KMM3S` pada uji lama**;
  identitas board harus dikonfirmasi operator sebelum membuka port.
- `fuser` tidak menemukan proses pemilik port, ModemManager dan
  serial getty tidak aktif, `vcgencmd get_throttled=0x0`.
- **Log kernel:** FT232R tersambung 02:28:39, USB disconnect 02:29:11,
  kemudian tersambung lagi 02:31:11 WIB. Ini adalah bukti gangguan
  koneksi yang perlu dijelaskan; jangan menyebut USB stabil hanya
  berdasarkan satu hasil enumerasi. Riwayat G3 Oktober juga pernah
  mengalami kegagalan kontroler USB setelah serial open.
- Semua pemeriksaan awal merupakan sysfs/SSH/diagnostik read-only,
  **tanpa** `open('/dev/ttyUSB0')`, DTR toggling, reset, flash,
  penekanan Nextion atau kendali pompa/valve.

## 2. Artefak model asli terpasang terpisah, tidak dipublikasikan

File yang diberikan pengguna ditemukan di Downloads workstation,
`final_model.joblib` dan `final_model_info.json`. Hash sebelum
transfer dan sesudah transfer pada Pi cocok:

```text
SHA256 final_model.joblib
b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d
Ukuran: 2363398 bytes
```

Model dan adapter disalin melalui SCP SSH ke folder **terisolasi** di Pi:
`/home/enose-v3/smart-coffee-stage7/rf30_staging/`. Tidak mengubah
service Stage7 lama, file `data/raw`, konfigurasi serial, layanan
systemd atau model di repo GitHub. File joblib **tidak di-commit**
karena berisi artefak binary pengguna dan mempunyai risiko eksekusi
kode melalui deserialisasi. Model hanya di-load setelah hash serta
metadata diperiksa dari sumber yang diberikan pengguna.

Virtualenv khusus `rf30_staging/.venv` berisi:

| Dependensi | Versi terpasang di Pi |
|---|---|
| Python | 3.13.5 |
| scikit-learn | 1.7.2 |
| NumPy | 2.5.4 |
| SciPy | 1.18.1 |
| joblib | 1.6.0 |

**Pengujian real model offline di Pi:**

- Contoh `D-CAT_B70.csv` sebanyak 900 baris (arsip existing,
  **bukan** sampel kopi baru / blind).
- Fitur persis dari script sumber, ADC absolut: TGS822 max mean
  `17699,0333`, TGS822 purging mean mean `17334,4627`,
  MQ8 max mean `17688,7`.
- Model asli RF500 berhasil dipanggil: **prediksi `dark`**,
  `predict_proba` (`dark=1.0, light=0, medium=0`).
  Probabilitas Random Forest **belum dikalibrasi** dan angka ini
  tidak boleh ditafsirkan sebagai tingkat kepastian atau akurasi blind.

## 3. Kode return protocol yang disiapkan

**Firmware source (belum di-flash):**

- `src/ai_rf30_return.h`: protokol pendek hanya untuk 3 kelas,
  format `#rf30:<8 hex uppercase>:<light|medium|dark>;`.
- `src/main.cpp`: token korelasi sesi AI Test pada `ACQ_START`,
  lalu setelah 30 siklus lengkap dan `ACQ_COMPLETE`,
  MCU mengirim `AI_AWAITING_RESULT`.
- MCU menerima paket hanya dalam jendela **30 detik**, pada
  `pResult`, dalam state `IDLE`, dengan token sesi sama.
  Duplikasi, label invalid, sesi salah dan timeout ditolak.
- Pada hasil yang diterima, `tRoast` akan menampilkan label,
  dan MCU memancarkan `AI_RESULT_ACK`. `tOrigin`, `tRConf`,
  `tOConf`, dan progress probabilitas tetap `N/A`/nol
  karena belum tersedia model origin dan kalibrasi probabilitas.
  Tata letak HMI **tidak diubah**.
- `ENABLE_PI_RF30_RETURN=0` secara default.
  Build compiler terpisah `scripts/platformio_rf30_bench.ini`
  menguji cabang fitur aktif (`=1`) **tanpa melakukan upload**.
  Token hanya **ID korelasi**, bukan autentikasi kriptografis.

**Host Pi:**

- `scripts/rf30_pi_result_bridge.py`: parser serial bounded,
  reject duplicate JSON/NaN/malformed, validasi session firmware,
  30 × 25+5, seluruh ADC, `ACQ_COMPLETE` dan handshake
  `AI_AWAITING_RESULT`. Hanya model SHA-pinned yang boleh
  menghasilkan paket kandidat. Mode live memiliki opt-in eksplisit
  dan binding ke path perangkat `/dev/serial/by-id`, serta
  **TIDAK DIEKSEKUSI** pada milestone ini.
- `scripts/pi_rf30_remote_preflight_readonly.py`: pemeriksaan
  perangkat/pi tanpa membuka serial.
- `scripts/pi_rf30_stage_selfcheck.py`,
  `scripts/pi_rf30_stage_model_verify.py`,
  `scripts/pi_rf30_stage_e2e_replay.py`: QA langsung di Pi,
  menggunakan SSH stdin.

**Replay dengan model asli langsung di Pi:**

1. Bangun aliran event firmware sintetis dari **900 ADC nyata** yang
   telah disimpan (bukan dari port USB live); AI Test tidak menyertakan
   label ground truth.
2. Host menerapkan validasi lengkap, menjalankan RF500 asli,
   membuat paket `#rf30:B1F503A9:dark;`.
3. Pemeriksaan ACK dari MCU dilakukan dengan **ACK simulasi**
   dan lulus. **0 byte dikirim** lewat UART dan layar Nextion fisik
   belum berubah.

## 4. Hasil pemeriksaan software dan batasnya

| Pemeriksaan | Status |
|---|---|
| SSH identity dan Pi sysfs preflight | PASS |
| Tailscale reachability dan port SSH | PASS |
| Enumerasi FT232R saat pemeriksaan | PASS (ada riwayat disconnect) |
| Model SHA256/metadata cocok di Pi | PASS |
| Pi venv terisolasi, model RF500 inference pada CSV real | PASS |
| Firmware `pio run -e mega2560` default release gate OFF | PASS |
| Firmware `pio run -e rf30_return_bench -c scripts/platformio_rf30_bench.ini` | PASS, compile-only |
| Native C++ packet parser / reject invalid | PASS |
| Simulasi Pi → paket UART → MCU ACK | PASS (MCU ACK mock) |
| Model → paket UART aktual, di Pi melalui replay | PASS (offline) |
| Bukti identitas PCB dari operator + safety G0/G2 | **BLOCKED** |
| Membuka USB serial / flashing ATmega / mulai 30 siklus | **NOT RUN** |
| Hasil RF pada pResult LCD fisik | **NOT RUN** |
| Blind prospective model performance / unknown rejection | **NOT VERIFIED** |

Pada build source nonaktif, MCU tetap menampilkan `N/A` walaupun
sesi lengkap. Ini disengaja: **jangan menyamakan logika yang selesai
di-code dengan fitur yang sudah aman untuk diaktifkan secara fisik**.

## 5. Urutan aman untuk G2/G3 sesudah verifikasi onsite

1. Operator memastikan **FT232R serial A10KNJBL** adalah benar alat
   Smart Coffee yang ingin diuji, dan menjelaskan disconnect–reconnect
   02:29–02:31. Periksa skematik daya/VBUS, ground, catu daya,
   dan kondisi PCB idle serta personel yang mendampingi.
2. Sesudah SOP dan persetujuan spesifik, lakukan **G2** pembacaan
   read-only singkat untuk membuktikan `FW_HELLO` perangkat fisik
   (jangan melakukan firmware upload sebagai bagian dari G2).
3. Bandingkan build ID MCU dengan source baru. Jika berbeda,
   siapkan backup firmware/EEPROM dan rencana pemulihan,
   kemudian lakukan flashing hanya setelah gate SOP terpisah.
4. Validasi G3 **satu kali** selama 900 detik di bawah pengawasan:
   cek 900 sampel, fase 25/5, timeout, disconnect, dan aktuator.
5. Setelah komunikasi dasar terbukti, uji return protocol dengan
   bench build ber-gate (bukan langsung produksi). Konfirmasi
   tampilan `pResult` oleh operator dan hasil N/A pada kegagalan.
6. Model RF hanya menjadi final setelah evaluasi independen
   berdasarkan batch/perangkat/sesi, model unknown, dan
   kalibrasi probabilitas.
