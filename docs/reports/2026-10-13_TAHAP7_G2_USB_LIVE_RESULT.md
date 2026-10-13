# Tahap 7 — Hasil nyata G2 USB serial PCB custom ATmega2560 → Raspberry Pi 5

**Tanggal tes:** 13 Oktober 2026 (WIB)
**Perangkat:** PCB custom Smart Coffee E-Nose, USB Type-B → FTDI FT232R
→ port USB-A Raspberry Pi 5, **bukan** testbed Arduino Mega Serial1.
**Kesimpulan:** **USB SERIAL PHYSICAL TRANSPORT PASS (RX)**;
**JSON/session-level E2E belum PASS**; G3 dan inferensi AI **NOT RUN**.

## Konfirmasi operator setelah uji G2 (13 Oktober 2026)

Sesudah tes G2 selesai, operator yang mengamati alat
menyatakan **"alat tetap normal seperti biasanya"**.
Ini adalah **bukti observasi operator bahwa tidak ada
gangguan fungsi yang terlihat**, bukan pengukuran
reset-pin, uptime, status internal ATmega atau
arus balik USB. Tidak ada gejala abnormal yang
dilaporkan operator selama atau setelah probe.

**Interpretasi terkini:** G2 USB transport
**PASS**, observasi operasional setelah tes
**NORMAL menurut operator**, kemungkinan
auto-reset DTR **belum dapat disangkal ataupun
dipastikan**. Status classifier saat live
`SERIAL_DATA_INCONCLUSIVE` tetap dipertahankan
karena ada pesan plain-text/non-JSON yang belum
diidentifikasi per baris dan **0 frame sampel**.
Kondisi normal tidak otomatis memberi izin
G3 akuisisi dengan pompa/valve.

## 1. Izin dan pengamanan aktual

Pembuat PCB telah menyatakan desain PCB aman (attestation operator,
bukan hasil pengukuran independen arus balik USB). Operator selanjutnya
mengonfirmasi **alat tetap menyala dan tidak sedang mengambil data**
serta secara eksplisit meminta **membuka port USB 12 detik dengan
risiko auto-reset ATmega diterima**. Status pengawasan fisik di lokasi
tidak diukur/dibuktikan secara independen oleh software SSH.

Sebelum membuka port, Pi SSH `enose-v3@enose-pi5` menunjukkan
FTDI FT232R VID:PID `0403:6001`, by-id
`usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`
→ `ttyUSB0`; `fuser` tidak menunjukkan pemilik port,
`serial-getty` dan `ModemManager` inactive,
`vcgencmd get_throttled=0x0`.
Regresi probe Python **PASS** sebelum tes.

Instrumen: `scripts/stage7_usb_readonly_probe.py`, live mode
`115200` baud, `8N1`, `exclusive=True`,
`dtr=False`, `rts=False` sebelum open, durasi
**12 detik**, baca maksimal 128 byte per call,
agregasi baris LF sampai 4096 byte. Skrip **tidak
memiliki jalur kirim serial/user commands**;
tidak mengirim `#start;`, `#scan;`, konfigurasi
Nextion, perintah aktuator, atau inferensi AI.
Pembukaan/penutupan serial tetap mungkin
memberi efek DTR/reset dari rangkaian hardware.

## 2. Bukti pengujian fisik nyata

File asli **tersimpan di Raspberry Pi**, dan tidak ditimpa:

```text
/home/enose-v3/smart-coffee-stage7/results/pi_stage7/custom_pcb_usb_g2_first_run.json
```

SHA256 file hasil Pi: `b4d8664703e21aa70f7ca0c61e4596f79551cd1172c8681c6d1628df22d7f2f3`

SHA256 skrip: `8e0771ea8b5a1ab4ee13eb13f20cb91901814f7c845bcb26be0ba5f9374c9495`

| Metrik | Hasil live |
|---|---|
| Port dibuka | **YA**, FT232R by-id → /dev/ttyUSB0 |
| Data masuk | **4.313 byte** |
| Baris lengkap | **33** |
| `other_json` | **14 baris** |
| `i2c_found` | **5 baris** |
| `i2c_scan_done` | **1 baris** |
| `invalid_json` | **13 baris** |
| Frame `valid_sensor_sample` | **0** |
| Frame terlalu panjang | **0** |
| Perintah dikirim dari Pi | **0** |
| Perintah aktuator dikirim | **0** |
| Model AI dipanggil | **TIDAK** |
| Akuisisi dipicu dari Pi | **TIDAK** |
| Power Pi setelah tes | `throttled=0x0` |
| Port owner sesudah tes | tidak terdeteksi |

Probe merekam **hash dan metadata frame**, bukan isi
lengkap payload. Karena tidak semua raw line tersedia,
13 baris non-JSON **tidak boleh diklaim pasti**
sebagai pesan firmware tertentu.

## 3. Interpretasi teknis dan pemeriksaan source

1. **Transport fisik USB FT232R → Pi terbukti hidup.**
   Port berhasil dibuka 12s, ada 4.313 byte dan
   20 baris yang valid secara struktur JSON
   (14 other_json + 5 i2c_found + 1 i2c_scan_done).
   Ini bukan sekadar enumerasi USB.
2. **Pola I2C scan konsisten dengan startup firmware**:
   `src/main.cpp` pada `setup()` membuka
   `Serial.begin(115200)`, memulai Nextion,
   memanggil `actuator.begin()` (pada source
   `stop()`), melakukan `scanI2C()`,
   kemudian `printWelcome()`. Deteksi lima
   perangkat I2C **tidak otomatis membuktikan**
   sensor semuanya valid, sehat, atau
   semua mengeluarkan data yang benar.
3. **13 baris invalid JSON mungkin memang diagnostik
   plain-text yang disengaja**. Source
   `printWelcome()` mencetak header,
   garis pemisah, dan daftar perintah
   sebagai teks biasa, bukan JSON.
   Ini kandidat penjelasan yang kuat,
   **tetapi tidak terverifikasi satu per satu**
   karena probe merekam hash alih-alih raw.
   Oleh karena itu hasil classifier saat run
   `SERIAL_DATA_INCONCLUSIVE` **dipertahankan
   apa adanya**, tidak diganti diam-diam.
4. **Tidak ada sampel sensor** pada tes 12 detik
   konsisten dengan alat dalam kondisi IDLE.
   Pada source `adsCallback()`, frame sensor
   hanya dikirim ketika state PURGING atau
   COLLECTING. Untuk mendapat frame live,
   diperlukan tes akuisisi fisik **G3 terpisah**;
   **jangan mengirim `#start;`** tanpa izin.
5. **Kemungkinan auto-reset**: munculnya
   inventaris dan banner awal konsisten
   dengan MCU menjalankan `setup()`.
   Namun, tanpa observasi reset pin/uptime
   atau keadaan sebelumnya, **tidak bisa
   dibuktikan** bahwa port open adalah
   penyebab restart; firmware terpasang
   mungkin tidak identik dengan source.
   Dampak UI/aktuator fisik harus
   dikonfirmasi operator di lokasi.

## 4. Keputusan gerbang dan tindak lanjut

| Gerbang | Status |
|---|---|
| G0 kelistrikan PCB | **Attestation operator diterima; pengukuran independen tetap belum ada** |
| G1 kabel USB | **Terhubung/terenumerasi** |
| G2 USB serial dapat dibuka dan mengirim byte | **PASS — live physical 12s** |
| G2 validasi semua payload JSON | **PARTIAL — ada plain text/invalid JSON, raw belum disimpan** |
| G2 data sensor real-time saat IDLE | **Tidak ada; sesuai kemungkinan perilaku firmware saat IDLE** |
| G3 Nextion mulai 5-siklus dan pompa/valve | **NOT RUN** |
| G4 handoff Pi→ATmega→Nextion/AI nyata | **NOT RUN** |
| AI model release | **NO-GO**; tidak berubah |

**Pilihan berikutnya:** setelah operator memastikan
tidak ada dampak reset/kelainan alat dan siap mengawasi
aktuator, minta izin G3 khusus untuk satu sesi
akuisisi melalui Nextion (±150s); pendengar Pi
akan dibuat dengan framing tahan timeout,
fail-closed, penyimpanan evidence baru tanpa
menimpa raw CSV. Jangan otomatis mengaktifkan
G3 hanya berdasarkan PASS G2.
