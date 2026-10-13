# Tahap 7 G3 — Satu percobaan akuisisi Nextion pada PCB custom

**Tanggal:** 13 Oktober 2026, Raspberry Pi lokal WIB

**Keputusan:** **G3 INCONCLUSIVE / NOT_STARTED**, bukan PASS.
Raspberry Pi menerima aktivitas USB serial, tetapi tidak
mendeteksi `ACQ_START` yang memenuhi kontrak, tidak
memvalidasi kelima siklus, dan tidak menemukan terminal
akuisisi. Tidak ada rilis model AI.

## 1. Izin dan prosedur

- Operator secara eksplisit menyetujui G3 **satu sesi**
  akuisisi via Nextion. Instruksi kepada operator: mulai
  **AI TEST** dengan satu kali START melalui LCD sesudah
  listener Pi berjalan, dalam kondisi uji udara bersih,
  tetap mengawasi pompa/valve.
- Python di Raspberry Pi **tidak mengirim perintah**
  `#start;`, `#stop;`, event HMI, perintah pompa/valve,
  firmware upload, atau panggilan model AI.
- Preflight: FT232R by-id `A10KMM3S` tersedia,
  port ttyUSB0 tidak sedang dipakai oleh proses lain,
  getty inactive, `get_throttled=0x0`,
  regresi `test_stage7_pi_adapter.py` PASS.
- SSH nama host pertama kali timeout; sambungan
  dipulihkan melalui alamat Tailscale
  `100.103.211.125` **dengan HostKeyAlias=enose-pi5
  dan StrictHostKeyChecking=yes**, sehingga verifikasi
  kunci host tetap berlaku.

## 2. Evidence yang benar-benar dihasilkan

Listener:

```text
.venv/bin/python scripts/stage7_pi_adapter.py serial-readonly
--port /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0
--baud 115200 --duration 180
--acknowledgment I_APPROVE_USB_SERIAL_READONLY
--output results/pi_stage7/custom_pcb_usb_g3_nextion_run01.json
```

File hasil **asli masih ada di Pi**:

```text
/home/enose-v3/smart-coffee-stage7/results/pi_stage7/custom_pcb_usb_g3_nextion_run01.json
```

SHA256 hasil:
`304234c8f950932bc5a907b0b1ff3c8411ace1c32c1f79ecae63738025862748`

| Pemeriksaan | Temuan |
|---|---|
| `hardware_serial_opened` | `true` |
| Baud dan port | FT232R by-id, 115200 |
| Durasi | batas maksimal 180 detik |
| `input_frames_read` | **304** nonempty read chunks yang diteruskan ke tracker, **bukan** 304 sampel valid |
| `terminal_event_count` | **0** |
| `final.quality` | **NOT_STARTED** |
| `final.status` | **N/A** |
| `final.reason` | **no_completed_session** |
| `release_gate` | **NO_GO_PENDING_LOCAL_VALIDATION** |
| Port setelah sesi | `fuser /dev/ttyUSB0` tidak menemukan pemilik |
| Kondisi daya setelah sesi | `throttled=0x0` |

**Tidak ada evidence aktual bahwa `ACQ_START` atau
`ACQ_COMPLETE` diterima**, sehingga tidak ada angka
kelengkapan lima siklus atau sampel kopi yang valid.
Bridge pada mode pasif tidak menyimpan payload serial
mentah pada file ini. Maka 304 chunks tidak dapat
ditentukan satu per satu apakah banner, log, JSON lain,
atau frame yang terfragmentasi.

## 3. Penilaian dan tindakan aman

1. USB FT232R → Pi tetap terhubung pada uji ini,
   tetapi **keberhasilan komunikasi tidak sama
   dengan keberhasilan akuisisi**.
2. Alat dapat belum ditekan START ketika listener aktif;
   atau firmware yang benar-benar terpasang mungkin
   menghasilkan format `ACQ_START` berbeda.
   **Kedua hal itu hipotesis**, bukan penyebab yang
   sudah terbukti.
3. Tidak dilakukan auto-retry atau kontrol dari Pi
   setelah batas listener habis. Firmware/Nextion,
   aktuator, EEPROM, dataset raw dan model AI
   tidak diubah.
4. Sebelum G3 ulang, konfirmasikan dengan operator:
   **apakah satu kali START ditekan saat listener aktif,
   dan apa yang dilihat di LCD / apakah pompa/valve
   menjalankan lima siklus**. Jika perangkat masih
   menjalankan siklus, tunggu selesai/hentikan
   secara aman sesuai SOP fisik.
5. Jika dilakukan retry setelah konfirmasi,
   siapkan listener dengan logging frame terstruktur,
   byte framing tahan timeout, durasi cukup dan
   output evidence dengan nama **baru**; hindari
   memulai dua sesi bersamaan dan jangan membuat
   file CSV kopi berlabel tanpa metadata operator.

**Status akhir:** satu percobaan G3 belum
memenuhi kriteria PASS. Tidak ada klaim
E2E Nextion→ATmega→Pi lengkap atau
performa AI produksi.
