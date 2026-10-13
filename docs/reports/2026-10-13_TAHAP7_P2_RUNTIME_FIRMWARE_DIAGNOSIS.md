# Tahap 7 P2 — diagnosis firmware runtime dan frame IDLE

**Tanggal pemeriksaan:** 13 Oktober 2026, 20:42–20:49 WIB.
**Perangkat:** Smart Coffee E-Nose PCB custom ATmega2560 → FT232R
USB serial `A10KMM3S` → Raspberry Pi 5 `enose-pi5`.
**Batas:** tidak ada flashing, aktuasi Pi, pengujian AI TEST
aktif, modifikasi TFT/EEPROM/data raw, atau pergantian kabel.

## 1. Bukti live baru — dua sesi receive-only

**Sesi 15s, parser sebelumnya dengan reason-code:**

- Evidence Pi: `results/pi_stage7/custom_pcb_usb_idle_reason_run02.json`.
- SHA256: `b72077a646210908833f22edace21a43ffddbd3f31fc2342d6184b9c08d268f0`.
- Serial opened, 5.026 bytes / 45 chunks / 38 newline frames;
  24 JSON lain, 14 malformed non-JSON startup banner;
  14 frame dengan seluruh 10 ADC+metadata sensor;
  **14/14 ditolak `invalid_phase`**, 0 event, 0 sensor valid.
- `NOT_STARTED` adalah hasil sesi saat IDLE, bukan kegagalan
  membuka port. Port tetap terenumerasi setelah uji.

**Sesi 8s, parser terbaru dengan kategori fase:**

- Evidence Pi: `results/pi_stage7/custom_pcb_idle_phase_enum_run03.json`.
- SHA256: `627f50c5c2460923dc09df2a4bbdb62fd40c8eccc0c0119684fa459d3d32be93`.
- Serial opened, 3.043 bytes / 34 chunks / 31 newline frames;
  17 JSON lain, 14 malformed non-JSON startup banner;
  **7 frame sensor-shaped, seluruhnya `phase=idle`**;
  `invalid_phase=7`, 0 sensor valid, 0 event wire,
  0 `nextion_event` (operator tidak menekan tombol).
- Setelah uji: FT232R tetap Bus 003 Device 002,
  `/dev/ttyUSB0` tersedia, `fuser` kosong,
  `get_throttled=0x0`, tidak ada USB disconnect yang
  tercatat pada log kernel boot baru.
- TX Pi ke MCU=0, ACTUATOR=0, model invoked=false.

**Interpretasi:** FT232R USB receive berfungsi pada dua
uji pasif baru dan fase yang ditolak **terkonfirmasi `idle`**.
Frame IDLE tidak boleh diterima sebagai sensor aktif untuk
data kopi, sesuai kontrak `acquisition_schema.is_sensor_payload`.

## 2. Riwayat firmware — bukti statis vs hardware

- `git show 75cb38a^:src/main.cpp` memperlihatkan implementasi
  lama `adsCallback()` melakukan `sensors.readAll();
  processAcquisitionState(); acqSampleIdx++;` lalu memanggil
  `sensors.printJsonData(acqStateName(), acqCycle, acqSampleIdx);`
  **tanpa guard fase aktif**. Konsekuensinya, ketika MCU IDLE,
  source lama memang mengeluarkan frame `phase=idle` tiap
  callback ADS 1000ms.
- Setelah commit `75cb38a` (9 Oktober 2026), source melakukan
  `printJsonData()` **hanya** ketika fase `COLLECTING` atau
  `PURGING`; callback tetap membaca ADC tetapi tidak
  mengeluarkan sensor JSON ketika IDLE/PAUSED.
- Kedua source menyertakan event `ACQ_START` dari
  `startAcquisition()`, event transisi fase, dan completion;
  source lama memasukkan label UI di `ai_test` yang kini
  secara sengaja ditolak validator untuk mencegah label leak.
- **Konsistensi kuat, bukan fingerprint binary yang unik:**
  stream live IDLE cocok dengan perilaku source sebelum
  `75cb38a`. Namun binary yang di-flash ke MCU dan
  nomor commit saat flash **belum diketahui**. Kode lain
  yang setara bisa menghasilkan gejala serupa.
- Startup banner/I2C scan muncul setiap pembukaan serial;
  ini **konsisten** dengan MCU reset melalui DTR atau
  inisialisasi, bukan bukti pengukuran reset-pin.

## 3. Perbaikan aman host

Pada `scripts/stage7_pi_adapter.py`, metadata sekarang
menyimpan dua counter tambahan berbasis fixed-enum:

- `sensor_like_phase_categories`: hanya `idle`, `paused`,
  `complete`, `purging`, `collecting`, atau
  `unknown_or_noncanonical` untuk bentuk sensor lengkap,
  **termasuk frame valid yang diterima saat fase aktif**.
- `nextion_event_categories`: hanya daftar event Nextion
  dikenal (`EVT:AI_START`, `EVT:AI_CANCEL`, `EVT:HMI_READY`,
  `EVT:HOME`, `EVT:TEST_START`, `EVT:DATA_START`) atau
  `OTHER_NEXTION_EVENT`.

Tidak merekam nilai ADC, isi event tak dikenal, label,
raw UART, atau menaikkan `idle` menjadi sensor valid.
Tes penolakan string rahasia, dataset replay,
framing, fail-closed, dan overflow ditambah/dipertahankan.

## 4. Verifikasi dan batas QA

- Windows: `test_stage7_pi_adapter.py`, `test_stage7_bridge.py`,
  `test_stage7_usb_readonly_probe.py`, `test_stage8_offline_e2e.py`,
  `test_stage6_release_gate.py`, `test_stage1_firmware_contract.py`,
  `compileall` dan `git diff --check` **PASS**.
- Build offline PlatformIO `mega2560` dan `nextion_test`
  **SUCCESS**; verifikasi 12 halaman/23 event HMI **PASS**.
- Pi: file listener dan tes **final** SHA256 identik dengan Windows:
  adapter `2a607904d269d2ec78585fec1c2a20fe7e3979497310aa2b00a1e08e3487d56a`;
  tes `591d6d7acc2075c573b48dd527a8f57ff6ddaf33cdcdbf05bd6de71cf3241c9e`.
  Regresi adapter/bridge/USB guarded probe/Stage8 offline Pi **PASS**.
  Pengujian tambahan memastikan frame valid dengan `phase=purging`
  juga dihitung pada `sensor_like_phase_categories`, tidak
  hanya frame yang ditolak.
- USB fisik PASS **khusus pengujian baca pasif tersebut**.
  Kontinuitas USB dan skema fase 150s selama G3 belum diuji.
- HMI verifier memunculkan warning deprecation Pillow,
  bukan error hasil kontrak. Model AI tetap NO-GO.

## 5. Rencana verifikasi G3 berikutnya (jangan auto-run)

**Pra-kondisi:** operator onsite dan menegaskan PCB/Nextion
aman, benar-benar IDLE, pompa/valve/selang normal, USB/PSU
stabil; preflight by-id, port owner, throttle, kernel,
checksum listener, nama evidence baru. Jika fail → STOP.

**Satu run terawasi** (150s nominal + margin, max 180s):
mulai Pi listener dahulu, operator menekan sekali
START AI TEST pada LCD. Pi hanya RX. Analisis per lapis:

1. `nextion_event_categories.EVT:AI_START` menunjukkan
   perintah Nextion diterima/dicetak MCU (jika firmware
   terpasang menyediakan metadata itu).
2. `wire_events_seen.ACQ_START` harus muncul. Jika event
   ada tetapi ditolak karena label legacy, koreksi via
   protokol yang aman atau lakukan firmware upgrade
   **ber-SOP dan backup**, jangan diam-diam hapus label
   lalu pakai sebagai ground truth AI.
3. `sensor_like_phase_categories` saat aktif harus
   `purging`/`collecting`, dan `valid_sensor_frames_seen`
   harus naik. Frame IDLE tetap dihitung diagnostik saja.
4. Periksa 5 siklus berurutan, `ACQ_COMPLETE`, indeks dan
   timestamp, nominal 150 sampel/variance, lalu
   `final.quality=COMPLETE_QA`. Bila satu kriteria gagal,
   status **INCONCLUSIVE/PARTIAL/FAIL**, bukan PASS.

**Keputusan:** tidak ada dasar meng-upload firmware otomatis
atau memaksa G3 PASS tanpa operator di sisi perangkat.
Status: **USB pasif PASS terbatas; IDLE phase diagnosed;
suspected on-device firmware drift; G3 INCONCLUSIVE;
AI_TEST N/A; model promotion NO-GO**.
