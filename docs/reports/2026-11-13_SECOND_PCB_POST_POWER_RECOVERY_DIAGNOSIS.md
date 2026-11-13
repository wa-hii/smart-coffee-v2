# Diagnosis ulang PCB kedua setelah perbaikan catu daya Raspberry Pi 5

**Tanggal:** 13 November 2026, sekitar 18.39–18.43 WIB.
**Branch:** `wahyu`.
**Target:** PCB custom ATmega2560 **kedua**; FT232R serial `A10KNJBL`
terhubung ke Raspberry Pi 5 melalui `/dev/ttyUSB0`, bukan Windows COM11.

## 1. Latar belakang dan batas

Operator memastikan catu 5 V custom sudah kembali aman dan
meminta melanjutkan diagnosis Nextion yang terakhir dilaporkan
tertahan pada **`Initializing Systems`**. Pemeriksaan sebelumnya
tercatat pada:

- `docs/reports/2026-11-13_SECOND_PCB_FIRMWARE_ID_AND_ROOT_CAUSE.md`
- `docs/reports/2026-11-13_SECOND_PCB_POWER_STOP_CONDITION.md`
- `docs/reports/2026-11-13_SECOND_PCB_POWER_RECHECK_CUSTOM_5V.md`

Kegiatan ini **hanya read-only**. Tidak ada reboot/reset sengaja,
flash, EEPROM read/write, pengiriman perintah USB ke MCU,
akuisisi, kontrol pompa/valve, penggantian firmware Nextion,
atau aktivasi RF500. Pembukaan port UART pasif tetap memiliki
kemungkinan glitch DTR dari driver/hardware yang tidak dapat
sepenuhnya dikesampingkan.

## 2. Hasil pemeriksaan daya pada boot terbaru

Pada pemeriksaan langsung sekitar 18.39 WIB:

```text
date Pi:               2026-11-13T18:39:17+07:00
uptime -s:             2026-11-13 18:38:30
vcgencmd get_throttled: throttled=0x0
EXT5V_V PMIC:          5.11746000V
vcgencmd measure_temp: temp=36.7'C
```

Pi telah melakukan **boot baru** sebelum pemeriksaan ini
(tidak diperintahkan oleh proses diagnosis).
Flag `get_throttled=0x0` berarti tidak ada flag
undervoltage/throttling **aktif maupun historis**
pada boot ini. Catatan kernel boot terbaru yang diperiksa
tidak memuat `Undervoltage detected!`.

Lima sampel tambahan PMIC saat idle:

| Pukul WIB | `EXT5V_V` | `get_throttled` |
|---|---:|---|
| 18.40.18 | 5,14560 V | `0x0` |
| 18.40.20 | 5,11344 V | `0x0` |
| 18.40.23 | 5,12282 V | `0x0` |
| 18.40.25 | 5,12148 V | `0x0` |
| 18.40.27 | 5,12416 V | `0x0` |

Rentang **5,11344–5,14560 V**, rata-rata **5,12550 V**
untuk kelima sampel. Ini **PASS untuk kondisi idle yang diamati**,
bukan bukti suplai stabil saat pompa/valve bekerja
atau transien cepat. Pi tersambung lewat PSU custom,
tetapi rail ATmega dan LCD tidak diukur oleh PMIC Pi.

## 3. FT232R dan log serial pasif setelah catu pulih

Pada boot ini, `ls -l /dev/serial/by-id/` menunjukkan
FT232R serial `A10KNJBL` menuju `../../ttyUSB0`.
`fuser /dev/ttyUSB0` tidak menemukan pemegang port.
Sebelum uji, SHA256 skrip Python diagnosis pada laptop
dan staging Pi **cocok**, sehingga skrip yang dijalankan
terbukti sama dengan source versioned pada repo.

Skrip `scripts/pi_second_pcb_passive_id.py` dijalankan
**sekali** selama 30 detik pada **115200 baud** sesuai
`Serial.begin(115200)` pada `src/main.cpp:268`.
Skrip mengatur `dtr=False` dan `rts=False`
sebelum `open()`, serta sama sekali tidak
memanggil `write()`.

```text
status                  SELESAI
durasi_aktual_s         30.1
rx_bytes                0
fw_hello_seen           false
build_ids_claimed       []
uart_tx_bytes           0
usb_disconnect_baru     false
usb_event_baru_count    0
pesan_error             null
mcu_flash_verified      false
```

Log byte mentah diperoleh dari Pi dan disalin ke
direktori privat (di-ignore Git):

```text
private/second_pcb_pi_readonly/
  diagnostics_20261113_after_power_fix_passive_01/
    serial_pasif_mentah.bin
    ringkasan.json
```

SHA256 log mentah kosong:
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Nilai cocok dengan panjang file **0 byte**.
Pemeriksaan setelahnya mengembalikan
`get_throttled=0x0` dan `EXT5V_V=5.14426 V`;
tidak terlihat USB disconnect baru.

**Batas interpretasi:** `FW_HELLO` dalam source hanya
dikirim pada awal `setup()`, dan source tidak
mentransmisikan sampel ADC ke UART ketika
`acqState=IDLE` (`src/main.cpp:1510–1550`).
Listener sengaja tidak mereset MCU, sehingga 0 byte
**tidak membuktikan firmware ATmega berhenti**.
Versi firmware fisik tetap **UNKNOWN**; log tidak
membuktikan kegagalan ataupun keberhasilan pengiriman
`page pHome` lewat Serial2.

## 4. Audit hubungan Nextion dan ATmega

Kontrak offline masih PASS:

- Source: `Serial` 115200 untuk USB Pi;
  `Serial2` 9600 untuk Nextion.
- `nextion.begin(9600)` di awal `setup()`;
  `scanI2C()` / `sensors.begin()` default
  **sebelum** `scheduler.init()` dan
  `taskSerial.enable()` (`src/main.cpp:267–333`).
- `serialCallback()` baru mengirim
  `page pHome` setelah task serial hidup dan
  `millis() - nextionBootMs >= 3000`
  (`src/main.cpp:1311–1317`).
- Proyek HMI acuan: 12 halaman, 23 event,
  Nextion 9600 baud; verifikator offline PASS.
- Kandidat build RF30 dengan I²C timeout
  sudah tersedia, **belum terbukti terpasang
  pada PCB kedua**.

**Dua hipotesis yang tidak dapat dipisahkan
melalui UART0 idle:** (a) startup MCU tertahan
sebelum task serial (misalnya operasi I²C
tidak pernah kembali), atau (b) MCU
berjalan tetapi `Serial2` tidak sampai/
tidak diterima Nextion. Versi firmware
berbeda, masalah RESET/clock/catu PCB
juga tetap memungkinkan. Tingkat keyakinan
untuk penyebab fisik tunggal tetap **rendah**.
Masalah suplai Pi yang sebelumnya terbukti
**tidak sedang terjadi saat pemeriksaan ini**,
tetapi belum ada bukti bahwa suplai PCB
atau Nextion normal.

## 5. RF500 dan QA

Preflight Pi `pi_rf30_pi5_readiness.py`
menghasilkan **`HOST_STAGED_NOT_MCU_VERIFIED`**:
FT232R ada, checksum RF500 dan modul bridge
terverifikasi, dependensi Python tersedia,
`mcu_firmware_build_id_verified=false`,
`live_activation_allowed=false`.
RF500 **tidak diaktifkan**.

Uji lokal yang dijalankan:

- `python scripts/test_pi_second_pcb_passive_id.py` — PASS
- `python scripts/test_pi_rf30_pi5_readiness.py` — PASS
- `python scripts/test_rf30_boot_guard.py` — PASS
- `python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py` — PASS

Semua pass tersebut adalah QA **software/offline**,
bukan kelulusan MCU/Nextion fisik.

## 6. Keputusan dan gerbang tindakan fisik berikutnya

**Daya Pi saat idle: PASS pada boot terbaru.**
**FT232R USB Pi: PASS enumerasi dan pembacaan pasif.**
**Firmware ATmega PCB kedua: UNKNOWN.**
**Akar spesifik layar `Initializing Systems`: UNKNOWN.**
**RF500 live: DITAHAN.**

Tidak ada skematik/foto PCB kedua yang dapat
diverifikasi dari checkout repo. Tindakan berikutnya
yang menghasilkan bukti baru memerlukan operator onsite:

1. Konfirmasi layar **masih** menunjukkan `Initializing Systems`
   setelah catu membaik, serta pastikan aktuator idle dan
   tidak ada panas/bau abnormal.
2. Sediakan skematik atau foto kedua sisi PCB
   sehingga net RESET, Serial0, Serial2,
   I²C dan pemetaan konektor dapat diidentifikasi.
3. **Dengan operator dan persetujuan pengukuran
   rangkaian menyala**, observasi RESET/clock,
   SDA/SCL dan terutama TXD2 ATmega (baud 9600)
   pada startup untuk membedakan kode stuck
   dari masalah UART Nextion.
4. Jika perlu membaca Flash fisik,
   gunakan programmer yang terbukti mengakses
   ATmega2560 dan backup **Flash + EEPROM
   dari PCB kedua** sebelum mengusulkan flashing;
   tindakan programmer/reset dan flashing
   memerlukan persetujuan terpisah.

Tidak dilakukan klaim bahwa firmware telah
dipulihkan atau layar sudah berpindah ke `pHome`.
