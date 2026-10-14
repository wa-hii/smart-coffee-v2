# G3 fisik setelah reboot Pi: START Nextion terdeteksi, kontrak firmware ditolak

**Tanggal:** 14 Oktober 2026, WIB. **Keputusan:** `G3_NOT_PASS`;
START fisik terbukti melalui event USB tetapi host fail-closed.
Tidak ada inferensi model, output AI tetap `N/A`.

## Rangkaian evidence

1. Operator mengonfirmasi pengawasan di lokasi dan G0 daya menurut
   pemeriksaan onsite; hasil pengukuran VBUS tidak diterima sebagai
   evidence numerik tersendiri.
2. Setelah kegagalan xHCI pada 16:24, operator melakukan reboot Pi.
   Reboot yang teramati: `2026-10-14 16:33:59` WIB. FT232R
   `0403:6001` serial `A10KMM3S` kembali di `/dev/ttyUSB0`.
3. G2 read-only 10 detik pada Pi berhasil membuka port dengan
   3744 byte / 31 baris. Port tetap terenumerasi sesudah uji,
   `throttled=0x0`, tanpa indikasi disconnect pada filter log.
   Evidence `results/pi_stage7/g2_post_reboot_20261014_1636.json`
   SHA256 `cb111992f3ba148e12262cd4a08ea7184c836630b3b6461ea8cf932b24825053`.
4. Listener `stage7_pi_adapter.py serial-readonly` dibuka pada Pi
   selama maksimum 180 detik di PID 1742, USB FT232R masih stabil.
   Setelah listener dipastikan aktif, operator diminta dan
   mengonfirmasi menekan tombol **START AI TEST sekali** pada
   Nextion. Pi tidak mengirim START, STOP, atau kontrol aktuator.
5. Setelah durasi maksimum, listener keluar dengan status
   `STAGE7_PI_ADAPTER_NOT_STARTED`, exit code 2. Evidence
   `results/pi_stage7/g3_supervised_after_reboot_20261014_1638.json`
   SHA256 `4115f3cdcd22fb2ddc7c4522d5e1eac6b5a369d018752905b978888b2d4b8af4`.

## Diagnosis dari trace G3 yang benar-benar diterima

| Kategori | Teramati |
|---|---:|
| Byte USB diterima | 53.120 |
| USB read chunks nonkosong | 302 |
| Baris lengkap tersusun | 212 |
| JSON malformed | 14 |
| Frame gas valid (phase purging/collecting) | 99 |
| Frame mirip sensor dengan `phase=idle` | 80 |
| Fase `purging` teramati | 83 frame |
| Fase `collecting` teramati | 16 frame |
| Event `EVT:AI_START` | 1 |
| Event `EVT:TEST_START` | 1 |
| Event `ACQ_START` | 1 |
| Event `PHASE_CHANGE` | 6 |
| ACQ_START ditolak: `ai_test_label_leakage` | 1 |
| Firmware `FW_HELLO` | NOT_OBSERVED |
| `SESSION_FINAL` host | 0 |

`NOT_STARTED` merupakan **status internal validator** sebab
`ACQ_START` ditolak (terdeteksi mengandung metadata label pada
mode `ai_test`). **Bukan** bukti operator gagal menekan tombol;
`EVT:AI_START`, `EVT:TEST_START`, dan `ACQ_START` justru membuktikan
rantai START Nextion→ATmega→FT232R→Pi. Tidak ada bukti validasi
`ACQ_COMPLETE` dan lima siklus penuh selama interval listener;
durasi pengamatan dan START operator mungkin tidak mencakup
seluruh siklus. `phase=idle` yang ditolak juga konsisten dengan
firmware legacy yang berbeda dari source RC1, tanpa membuktikan
identitas binary MCU secara definitif.

## Gerbang dan tindakan lanjut

- **G2 USB post-reboot PASS** pada satu percobaan. Stabilitas
  jangka panjang dan reset DTR belum dibuktikan; jangan overclaim.
- **G3 diagnostik fisik PARTIAL, release/complete FAIL_CLOSED**.
  Tidak ada model dipromosikan; semua AI TEST tetap `N/A`.
- **Jangan relaksasi validator untuk meloloskan label leakage**.
  Bandingkan versi binary MCU yang benar-benar di-flash dengan
  firmware frozen `pre-onsite-software-2026-10-14-rc1`.
  `FW_HELLO` baru akan tersedia setelah firmware RC1 benar-benar
  diinstal. Flashing/ISP/read-back perlu SOP dan persetujuan
  khusus dengan operator onsite dan backup firmware bila memungkinkan.
- Setelah firmware/runtime diperbaiki dan USB G2 stabil, ulangi
  **satu** G3 dengan listener waktu yang memadai dan sinkronisasi
  START lebih cepat; setiap retry memakai evidence file baru.
- Software RC1 **tidak diubah** pada sesi ini.
