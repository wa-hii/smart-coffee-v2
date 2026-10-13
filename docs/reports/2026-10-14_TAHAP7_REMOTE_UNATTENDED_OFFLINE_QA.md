# Tahap 7 — remote unattended, offline G3 protocol QA

**Waktu:** Rabu 14 Oktober 2026 sekitar 05:34–05:37 WIB.
**Kondisi operator:** mengonfirmasi Pi dan PCB custom ATmega
menyala dan dapat diakses remote, **tetapi tidak berada di
dekat alat**. Supervisi fisik pompa/valve, selang, kelistrikan,
dan tombol emergency stop tidak tersedia.

## 1. Batas keselamatan eksekusi

- **Tidak dilakukan** USB serial open, START AI TEST,
  perintah `#start`, set GPIO, aktuasi pompa/valve,
  reset/reboot MCU/Pi, PlatformIO upload, pengubahan TFT,
  EEPROM, atau data mentah.
- Alasan: serial open **sendiri** dapat me-reset MCU via
  DTR; START lima siklus nominal 150 detik akan menggerakkan
  aktuator tanpa pengawasan. Insiden FT232R disconnect
  13 Oktober sebelumnya juga belum memiliki RCA fisik final.
- Pengujian terbatas pada observasi perangkat **non-invasif**
  (`lsusb`, symlink, pemilik port, throttling, kernel log)
  dan komputasi offline Windows/Pi.

## 2. Preflight Pi terkini (observasi langsung)

`enose-pi5`, SSH dengan host key checking, waktu sekitar
`2026-10-14T05:34:28+07:00`.

- Pi uptime sejak `2026-10-13 19:49:19 WIB`.
- `lsusb -d 0403:6001` menampilkan Bus 003 Device 002,
  FT232R UART; by-id `usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`
  → `/dev/ttyUSB0`.
- `fuser /dev/ttyUSB0` tidak mencantumkan owner;
  getty dan ModemManager inactive.
- `vcgencmd get_throttled` = `throttled=0x0`.
- Kernel log boot memperlihatkan attach 13 Oktober 19:49:22,
  tanpa indikasi disconnect baru pada pemeriksaan.
- Ini **bukan** bukti bahwa serial port telah dibuka dan
  mampu menerima stream aktif selama 150 detik pada hari ini.

## 3. Perbaikan diagnostik protokol

Riwayat kode membuktikan `startAcquisition()` pada source
**sebelum** `75cb38a` mengirim `sample_id`, `roast_level`,
`origin_code`, `batch_id`, dan nama file **meski mode `ai_test`**.
Source `75cb38a` ke atas membatasi field label tersebut
ke `labeled_data`. Firmware binary terpasang belum
diverifikasi, sehingga gejala live belum dapat disamakan
dengan commit tertentu secara pasti.

Penambahan di `scripts/stage7_pi_adapter.py`:

- `diagnostics.acq_start_contract_outcomes` merekam
  `accepted`, `ai_test_label_leakage`, `bad_start_contract`,
  atau `other_rejection` saat menerima wire event ACQ_START.
- Kategori disimpulkan dari hasil **bridge state validator**,
  tidak menyalin metadata sampel/label, baud, atau nilai ADC.
- Tes `test_stage7_pi_adapter.py` memverifikasi tiga keadaan:
  legacy leak ditolak fail-closed, start compliant diterima
  tapi stream putus → fail-closed, start dengan timing salah
  → kontrak ditolak. Nilai uji rahasia tak boleh muncul di JSON.
- Frame malformed tidak boleh memakai kembali event dari
  baris sebelumnya (`event=None` sebelum decode).
- Tidak melonggarkan sensor phase guard, tidak mengubah
  Stage6 release gate, tidak membuat model keluaran palsu.

## 4. Hasil pengujian offline aktual

Windows: `test_stage1_firmware_contract.py`,
`test_stage6_release_gate.py`, `test_stage7_bridge.py`,
`test_stage7_pi_adapter.py`,
`test_stage7_usb_readonly_probe.py`,
`test_stage8_offline_e2e.py`, Python compileall,
dan `git diff --check`: **PASS**.

Pi `.venv/bin/python`: adapter, bridge, guarded USB test,
Stage8 offline E2E: **PASS**.

**Replay CSV yang benar-benar dieksekusi di Pi:**

```sh
cd /home/enose-v3/smart-coffee-stage7
.venv/bin/python scripts/stage7_pi_adapter.py replay-csv \
  --input data/raw/D-GAW_B33.csv \
  --output results/pi_stage7/g3_unattended_offline_replay_20261014.json
```

- Source raw SHA256:
  `d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`
- Evidence Pi path:
  `results/pi_stage7/g3_unattended_offline_replay_20261014.json`
- Evidence SHA256:
  `f5290d843faccd7186a2e482177a6970a2baeb47711096742f1d792cce9d1ed3`
- `mode=replay-csv`, `hardware_serial_opened=false`.
- Bridge: `mode=ai_test`, `sensor_samples=151`,
  `quality=COMPLETE_QA`,
  `reason=five_cycles_checked_no_approved_model`,
  `nominal_150_samples=false`.
- AI output `N/A`, model invoked=false,
  sent_to_atmega=false, actuator_commands_sent=0,
  release gate `NO_GO_PENDING_LOCAL_VALIDATION`.

**Interpretasi:** sensor stream replay dari CSV existing
lolos kontrak lima siklus. Ada **151** sampel, jadi
ketepatan 150 sampel nominal tidak boleh diklaim;
bridge mengizinkan variasi tepi per fase dalam jendela
yang telah diuji. Ini hanya E2E software memakai real CSV,
**bukan pengujian fisik baru ataupun validasi ilmiah AI**.

## 5. Sinkronisasi dan gerbang keputusan

- Adapter Windows/Pi checksum SHA256:
  `b36d1fb4217853479da2642f75bd16e0c1fd2d9adf606b67803a0ffa3ed7c925`.
- Test adapter Windows/Pi checksum SHA256:
  `7ab4d50218318f0a837a4bb3c181d946d7bbbb8f6806aaa05b65ce108d13d98d`.
- Port FT232R tetap terenumerasi setelah seluruh test offline.
- **PASS:** preflight non-invasif, protocol regression, replay
  data nyata secara offline dan sinkronisasi software.
- **NOT TESTED:** START dari Nextion → USB, USB 150s,
  pompa/valve selama 5 siklus, live ACQ_COMPLETE, label
  metadata dari firmware yang benar-benar terpasang.
- **G3 live = INCONCLUSIVE**; model AI = `N/A`, deployment
  = NO-GO. Uji aktif baru memerlukan orang di lokasi yang
  dapat mengawasi dan mematikan perangkat jika ada anomali.

Tidak membuat klaim "alat sudah benar E2E" hanya dari
PASS replay. Tidak mengubah file mentah, platformio.ini
yang sudah dimodifikasi user, maupun hasil ML untracked.
