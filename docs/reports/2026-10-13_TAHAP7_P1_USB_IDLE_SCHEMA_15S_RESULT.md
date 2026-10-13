# Tahap 7 P1 — hasil USB read-only IDLE 15 detik setelah reboot

**Tanggal:** 13 Oktober 2026, preflight 20:19:41 WIB,
postflight 20:20:48 WIB. **Perangkat:** PCB custom Smart Coffee
ATmega2560 → FT232R (`0403:6001`, serial `A10KMM3S`) → Pi 5.
**Izin:** operator menjawab setuju untuk **satu kali** capture
read-only 15 detik dengan prasyarat alat IDLE/aman/diawasi.
Tidak ada pengujian lima siklus, perintah aktuator, atau firmware upload.

## Bukti live Pi (asli, tidak dimodifikasi)

`/home/enose-v3/smart-coffee-stage7/results/pi_stage7/custom_pcb_usb_schema_idle_15s_postreboot_run01.json`

SHA256: `479687224987356cb9ae5b391deb01fee92a64e86d63fc430fe0967c3ebc1818`.

Sebelum capture, SSH dengan host key tervalidasi, `uptime -s`
`19:49:19`, FT232R by-id → `ttyUSB0`, `fuser` kosong,
getty/ModemManager inactive, `get_throttled=0x0`. SHA256
adapter versi saat capture:
`5628304575b3d28d2234106b5f198e8670614b82301174206429df2b`.
Tes offline adapter dan bridge PASS di Pi sebelum pembukaan.

| Metrik (evidence aktual) | Nilai |
|---|---|
| Port serial benar-benar dibuka | `hardware_serial_opened=true` |
| Baud / batas durasi | 115200 / 15s |
| Byte diterima / chunk nonempty | **5.026 / 44** |
| Baris LF lengkap / partial tail / overflow | **37 / 0 / 0** |
| JSON valid / non-JSON | **23 / 14** |
| JSON 10 ADC + phase/cycle/idx/timestamp (key lengkap) | **14** |
| JSON I2C found / info / scan complete | **5 / 3 / 1** |
| Sensor yang lolos `is_sensor_payload()` | **0** |
| `ACQ_START` / `ACQ_COMPLETE` / event lain | **0 / 0 / 0** |
| Listener TX / penggerak aktuator / model | **0 / 0 / tidak dipanggil** |
| Kualitas host | `NOT_STARTED`, `N/A` (expected saat IDLE) |

Listener exit code `2` karena tidak ada sesi `COMPLETE_QA`,
**bukan** karena gagal membuka USB. Setelah capture, FT232R
tetap muncul di `lsusb` sebagai Bus 003 Device 002,
by-id dan `/dev/ttyUSB0` masih ada, `fuser` kosong,
`throttled=0x0`; log kernel boot baru hanya mencatat attach
19:49:22, tanpa USB disconnect lagi saat diperiksa.

## Interpretasi terukur

1. **Transport PASS untuk capture ini saja.** USB terbuka dan
   mengirim data ke Pi sampai sesi pasif selesai. Ini tidak
   menjamin stabilitas pada G3 berdurasi 150 detik.
2. **Field names sensor cocok dengan skema source**:
   `adc_tgs822`, `adc_mq135`, `adc_mq3`, `adc_tgs2611`,
   `adc_tgs2620`, `adc_tgs2600`, `adc_tgs2602`, `adc_mq8`,
   `adc_tgs813`, `adc_tgs816`, bersama `phase`, `cycle`,
   `sample_idx`, `timestamp`, `temperature_c`, `humidity_rh`.
   Tetapi **semua 14 frame ditolak sebagai sampel aktif**.
   Key-only evidence tidak menyimpan alasan spesifik per frame,
   nilai phase, idx, timestamp, ADC, atau data pribadi.
3. Pada source checkout saat ini, `src/main.cpp::adsCallback()`
   memanggil `printJsonData()` **hanya ketika state COLLECTING
   atau PURGING**. Dengan asumsi observasi operator benar-benar
   IDLE sepanjang capture, keluaran sensor-shaped 1 Hz itu
   **tidak dijelaskan oleh perilaku source tersebut**.
   Kandidatnya mencakup versi firmware PCB berbeda, state
   MCU aktual bukan IDLE, atau variasi perilaku/protokol lain.
   **Belum ada verifikasi firmware binary pada perangkat.**
4. Munculnya banner non-JSON dan scan I2C saat serial open
   **konsisten dengan kemungkinan reset/inisialisasi MCU**,
   tetapi perubahan DTR/reset tidak dipastikan lewat pengukuran.
5. G3 Run02 sebelumnya menerima 189 JSON lain pada 180s;
   kemiripan frekuensi dengan 14 frame/15s adalah **indikasi
   untuk diselidiki**, bukan pembuktian frame Run02 identik.

## Improvement host offline setelah capture

`scripts/stage7_pi_adapter.py` menambah
`sensor_like_invalid_frames_by_reason`: hitung kode penolakan
yang *allow-listed* (`invalid_phase`, `invalid_cycle`,
`invalid_sample_idx`, `invalid_timestamp`, atau nama field
ADC tidak valid). Tidak ada nilai yang diserialisasi;
frame sensor-shaped tetap ditolak fail-closed. Uji regresi
`scripts/test_stage7_pi_adapter.py` memeriksa skenario IDLE,
ADC invalid, dan bahwa string nilai rahasia tidak masuk JSON.
Peningkatan ini **baru berlaku bagi capture mendatang** dan
tidak dapat mengekstrak detail dari bukti yang hanya menyimpan key.

**QA dan deployment software-only setelah capture:**

- Windows: `test_stage7_pi_adapter.py`, `test_stage7_bridge.py`,
  `test_stage7_usb_readonly_probe.py`, `test_stage8_offline_e2e.py`,
  dan `compileall` **PASS**.
- Dua berkas Python diagnostik diperbarui pada workspace Pi melalui
  SCP dengan host key divalidasi. SHA256 adapter terbaru Windows/Pi:
  `96fdb89fd71753d9e6efa976746e78533ca94c4c87ea77f358b31adf1ed05816`;
  SHA256 test terbaru Windows/Pi:
  `ff0171e9e6c5a200c91556a98d3b24e2f798f999dc47a9e2f4c4f60ba1092843`.
- Pi: regresi adapter, bridge, dan Stage 8 E2E offline **PASS**;
  FT232R tetap terenumerasi. **Tidak ada serial open tambahan**.
- Hash versi adapter saat capture sebelumnya tetap tercatat
  apa adanya; perubahan software baru tidak berlaku surut.

## Kesimpulan dan gerbang selanjutnya

**G2/P1 USB read-only 15s PASS transport terbatas**;
**schema key discovery PASS**; **actual sensor validity INCONCLUSIVE**;
**G3 tetap INCONCLUSIVE**; **AI model promotion NO-GO**.

Untuk diagnosis berikutnya, pastikan keadaan fisik benar-benar
IDLE, identitas firmware terpasang (jika ada catatan upload),
dan keselamatan kabel/rail USB. Satu capture singkat dengan
diagnostik reason-code dapat membedakan invalid phase/index/ADC
**hanya dengan persetujuan hardware baru**, lalu putuskan apakah
perlu koreksi kontrak host atau pembaruan firmware lewat SOP.
**Jangan langsung menjalankan G3, flash, atau retry USB otomatis.**
