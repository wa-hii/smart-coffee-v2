# STOP: gangguan tegangan Raspberry Pi 5 terdeteksi saat tindak lanjut PCB kedua

**Tanggal:** 13 November 2026, pemeriksaan sekitar 18.06–18.15 WIB.
**Branch:** `wahyu`.
**Ruang lingkup:** pemeriksaan **read-only** atas status catu daya,
USB dan log kernel pada Raspberry Pi. Tidak ada pengoperasian sensor,
pompa, valve, reset, flash atau penulisan EEPROM.

## 1. Latar belakang

Operator meminta melanjutkan diagnosis Nextion PCB ATmega2560 kedua
yang tertahan di `Initializing Systems`. Hasil diagnosis sebelumnya:
`docs/reports/2026-11-13_SECOND_PCB_FIRMWARE_ID_AND_ROOT_CAUSE.md`.
Firmware fisik MCU masih belum teridentifikasi; FT232R serial
`A10KNJBL` tersedia di Pi; uji UART pasif 45 detik sebelumnya
menerima **0 byte** tanpa disconnect baru.

Tahap berikutnya semula direncanakan untuk memeriksa jalur
RESET, daya, Serial2 Nextion dan I²C. Tidak ditemukan file
skematik PCB yang terverifikasi di checkout repository; daftar
pin/protokol dalam dokumen tidak boleh dianggap sebagai hasil
pengukuran net PCB kedua.

## 2. Temuan penting yang mengharuskan STOP

Pada pemeriksaan read-only terbaru:

```text
vcgencmd get_throttled
throttled=0x50000
```

`0x50000` menandakan flag historis:
**undervoltage pernah terjadi** dan **throttling pernah terjadi**
sejak boot. Flag bit-status saat ini tidak aktif pada
nilai tersebut; **bukan bukti tegangan sedang rendah**
ketika perintah dijalankan.

Journal kernel boot memperlihatkan:

```text
Nov 13 18:06:52 enose-pi5 kernel: hwmon hwmon3: Undervoltage detected!
Nov 13 18:07:04 enose-pi5 kernel: hwmon hwmon3: Voltage normalised
Nov 13 18:07:09 enose-pi5 kernel: hwmon hwmon3: Undervoltage detected!
Nov 13 18:07:15 enose-pi5 kernel: hwmon hwmon3: Voltage normalised
```

Kedua kejadian terjadi pada boot yang diperiksa.
Perintah `uptime` pada pemeriksaan sekitar 18.15
menunjukkan uptime sekitar **2 menit**, sehingga
terdapat indikasi boot ulang sejak pengujian sebelumnya;
catatan wall-clock journal/uptime dapat dipengaruhi
sinkronisasi waktu sehingga jam boot ulang dan
penyebab reboot **belum dapat dipastikan**.

FT232R `A10KNJBL` masih terenumerasi melalui
`/dev/serial/by-id/...` → `/dev/ttyUSB0`,
dan `fuser /dev/ttyUSB0` tidak menemukan pemegang port.
Enumerasi USB **tidak** membuktikan rail ATmega,
Nextion, sensor maupun solenoid berada pada tegangan
yang benar.

## 3. Keputusan keselamatan dan dampak diagnosis

**STOP CONDITION TERPENUHI: indikasi berulang kegagalan
catu Raspberry Pi.** Tidak boleh melanjutkan uji
serial/reset, ISP/bootloader, flashing MCU/EEPROM,
pengujian I²C/Nextion berbasis perangkat menyala,
atau mengaktifkan pompa/valve sampai operator onsite
menyatakan suplai aman dan memberi persetujuan tindakan
fisik berikutnya.

**Tidak boleh menyimpulkan undervoltage Pi adalah
akar masalah pasti layar Nextion.** Apabila Pi dan
ATmega mendapat suplai yang berbeda, masalah catu
dapat berdiri sendiri. Namun temuan ini memperkuat
prioritas inspeksi kabel, PSU, kesamaan ground,
kemungkinan backfeed USB dan kestabilan tegangan
di bawah beban.

Tidak dilakukan reset, pemeriksaan serial lagi,
perubahan service/udev/boot Pi, ataupun flashing.
RF500 tetap `live_activation_allowed=false`.

## 4. Rencana pemeriksaan onsite untuk operator

1. **Sebelum menyalakan ulang:** hentikan pengujian,
   pastikan tidak ada komponen panas berlebih,
   bau terbakar, atau kabel rusak. Bila ada,
   putuskan daya secara aman dan jangan lanjutkan.
2. **Identifikasi suplai yang sedang dipakai** untuk
   Raspberry Pi 5, PCB ATmega, LCD Nextion, sensor
   dan aktuator; dokumentasikan jenis adaptor,
   rating arus, konektor USB-C, serta apakah
   USB PCB menyebabkan konflik suplai/backfeed.
3. **Dengan operator dan alat ukur yang sesuai:**
   konfirmasi rail Pi pada konektor daya,
   rail VCC/AVCC ATmega dan suplai Nextion sesuai
   skematik masing-masing; pemeriksaan alat
   menyala memerlukan persetujuan eksplisit dan
   pengawasan onsite. Jangan menjembatani
   sumber 5V yang berbeda tanpa verifikasi.
4. Setelah wiring/suplai diperbaiki dan dinyatakan
   aman oleh operator, minta izin untuk pemeriksaan
   read-only ulang pasca-start. Bandingkan
   `vcgencmd get_throttled`, `journalctl -k -b`,
   uptime, serta USB stability pada boot **baru**.
   Catatan: flag historis `get_throttled` baru
   dapat diinterpretasikan sebagai sesi baru
   setelah reboot terkontrol.
5. Setelah stabil, lanjutkan diagnosis boot
   MCU/I²C dan jalur Serial2 ke Nextion;
   jangan gunakan backup PCB COM5/SVM30
   atau mengaktifkan RF500 sebelum firmware
   PCB kedua benar-benar diidentifikasi.

## 5. Bukti dan status akhir

| Item | Hasil |
|---|---|
| SSH Pi | PASS |
| FT232R by-id ke ttyUSB0 | PASS enumerasi |
| `get_throttled` | **0x50000 — histori undervoltage dan throttling** |
| Journal kernel | **Dua kali undervoltage detected/normalised pada boot** |
| Firmware ATmega PCB kedua | UNKNOWN |
| Nextion pHome fisik | BELUM TERVERIFIKASI |
| Tes aktif hardware, programmer, Flash/EEPROM | **STOP / NOT RUN** |
| RF500 live | **DITAHAN** |

**Pertanyaan operator yang dibutuhkan:** Pada saat
kejadian undervoltage ini, Raspberry Pi diberi daya
melalui adaptor USB-C resmi berkemampuan 5V/5A,
atau menggunakan catu 5V dari rangkaian custom?
Ada panas berlebih, bau tidak normal atau LED
daya Pi yang berubah ketika LCD/PCB tersambung?

Jangan melakukan langkah perbaikan yang menuntut
perangkat hidup atau reset tanpa jawaban dan
persetujuan operator.
