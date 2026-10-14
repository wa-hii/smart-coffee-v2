# G3 RC2 — lima siklus fisik PASS setelah flash ATmega2560

**Tanggal:** 14 Oktober 2026, WIB, sekitar 18:19–18:23.
**Status QA akuisisi fisik:** **PASS**.
**Status AI/inferensi kopi:** **NO_GO; RESULT=N/A**.

## Prasyarat dan eksekusi

- Firmware source RC2 tag `pre-onsite-software-2026-10-14-rc2`
  telah di-flash ke ATmega2560 via COM5 dan diverifikasi AVRDUDE
  (34.930 byte flash), sebagaimana dicatat pada
  `2026-10-14_RC2_FLASH_COM5_ATMEGA2560_VERIFIED.md`.
- Operator memindahkan USB data kembali dari Windows ke Raspberry Pi 5,
  kemudian mengonfirmasi. Pi membaca FT232R `VID:PID=0403:6001`,
  serial `A10KMM3S` pada `/dev/ttyUSB0` setelah attach pukul 18:16:34.
- G2 USB read-only 10 detik: berhasil membuka port 115200 baud,
  menerima 1.109 byte/21 baris; klasifikasi konten probe
  `SERIAL_DATA_INCONCLUSIVE` (tidak diklaim sebagai bukti build).
  Evidence Pi: `results/pi_stage7/g2_rc2_post_flash_20261014_1818.json`.
- G3 listener Pi read-only: `scripts/stage7_pi_adapter.py`, checksum
  `1ac4859de6b2e7743f544d216d10b507fc85375715de138c8d231663e2879dae`,
  baud 115200, durasi maksimum 240 detik, port by-id FT232R.
  Listener PID 2154 dipastikan memegang port sebelum operator diminta
  menekan START. Operator mengonfirmasi START AI TEST ditekan satu kali.
  Tidak ada start via USB atau perintah aktuator oleh host.
- Listener keluar normal dengan **exit code 0**:

```text
G3_LISTENER_READY_USB_RX_ONLY
STAGE7_PI_ADAPTER_COMPLETE_QA
RESULT=N/A
```

## Bukti terminal dari Pi

Lokasi laporan lokal Raspberry Pi:

`/home/enose-v3/smart-coffee-stage7/results/pi_stage7/g3_rc2_supervised_after_flash_20261014_1819.json`

**SHA256 laporan:**
`3c17581dd2286b173cd5134ff732f7067703d5e5f9a888920c9d19f8b16411db`.

| Pemeriksaan | Hasil nyata |
|---|---:|
| Serial port berhasil dibuka | `true` |
| Total byte serial | 45.259 |
| Frame newline lengkap | 185 |
| Frame sensor valid | **150** |
| Frame phase `purging` | **125** |
| Frame phase `collecting` | **25** |
| Sensor frame ditolak karena skema | 0 |
| `EVT:TEST_START` Nextion | 1 |
| `EVT:AI_START` Nextion | 1 |
| `ACQ_START` diterima oleh validator | 1 |
| `PHASE_CHANGE` | 9 |
| `ACQ_COMPLETE` | **1** |
| `FW_HELLO` | `MATCHED` |
| `ACQ_START.fw_build_id` | `MATCHED` |
| `physical_g3_compatibility_verified` | `true` |
| `physical_g3_complete_verified` | **`true`** |
| `SESSION_FINAL.quality` | **`COMPLETE_QA`** |
| `SESSION_FINAL.sensor_samples` | **150** |
| `SESSION_FINAL.reason` | `five_cycles_checked_no_approved_model` |
| `SESSION_FINAL.status` | `N/A` |
| `terminal_event_count` | 1 |
| `listener_transmitted_bytes` | 0 |
| `model_invoked` | `false` |
| `model_promotion_allowed` | `false` |

Ada 11 baris `malformed_json_lines` yang dihitung sebagai diagnostik
di luar frame sensor valid; hal ini **tidak** mengganggu pengesahan
150 sampel yang memenuhi kontrak, tetapi tetap menjadi bahan audit
serial/boot banner. Adapter tidak menyimpan nilai sensor mentah.

Sesudah proses keluar, port `/dev/ttyUSB0` tidak lagi digunakan
listener, `lsusb` tetap menampilkan FT232R; Pi melaporkan
`get_throttled=0x0` dan tidak ada disconnect/xHCI failure baru
dari log kernel yang difilter sejak 18:18 WIB.

## Kesimpulan dan batas bukti

**G3 akuisisi fisik/transport lima siklus PASSED** untuk run tunggal
ini. Ini membuktikan event START Nextion, build RC2 yang dilaporkan
firmware, 150 sampel sesuai 5 × (25 purging + 5 collecting), fase
berurutan, dan `ACQ_COMPLETE` valid lewat FT232R ke Raspberry Pi.

**Tidak membuktikan:** konsentrasi aroma yang terkalibrasi,
repeatability lintas batch, kestabilan USB pada banyak run,
kesesuaian kondisi udara/kalibrasi sensor, validitas kopi/ground
truth atau akurasi model klasifikasi. `N/A` pada Roast Level,
Coffee Origin, Roast Probability adalah perilaku yang benar
karena gate AI belum terbuka. Perlu konfirmasi operator bahwa
LCD mencapai halaman Test Complete untuk menutup bukti visual
HMI pada run RC2 yang khusus ini.

**Tindak lanjut:** tanpa penulisan firmware atau operasi hardware
tambahan pada sesi penutupan ini, pertahankan tag RC2 dan bukti Pi,
lalu lakukan analisis kualitas data/model secara terpisah dengan
dataset berlabel dan validasi independen. Jangan mengganti `N/A`
menjadi prediksi/angka probabilitas tanpa evaluasi yang sah.
