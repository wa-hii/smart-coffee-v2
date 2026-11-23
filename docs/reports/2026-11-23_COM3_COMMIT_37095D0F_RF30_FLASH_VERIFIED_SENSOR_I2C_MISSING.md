# COM3 — firmware RF30 dari commit 37095d0f: build, backup, upload dan verifikasi berhasil

**Tanggal:** 23 November 2026 WIB.
**Perangkat:** FT232RL `USB VID:PID=0403:6001`,
serial `A10KN6X9A`, Windows `COM3`,
bootloader ATmega2560 `wiring/115200`.
**Hasil:** firmware berhasil di-flash dan diverifikasi, tetapi
**sensor I²C saat boot tidak terdeteksi** sehingga perangkat
belum siap melakukan Take Data/AI Test pada konfigurasi hardware ini.

## 1. Sumber dan hasil build

Operator meminta program dari commit **`37095d0f`**.
Hash commit penuh:
`37095d0fddb3be818405729a818e6cbf33cc9a0c`.

Checkout utama `wahyu` memiliki berkas kerja lain yang belum
di-commit sehingga **tidak di-reset atau dipindah branch**.
Git archive commit hanya mengambil `platformio.ini`,
`src/`, `include/`, `lib/`, dan `test/`, ke direktori
build terpisah di laptop:

```text
D:\ENOSE\_rf30_COM3_37095d0f\build\
```

Semua **93 berkas** source di archive diperiksa
byte-by-byte terhadap hasil ekstraksi: **0 perbedaan**.

Build pertama dengan opsi default commit sukses,
tetapi karena `ENABLE_PI_RF30_RETURN=0`,
hasil default tersebut **tidak dipilih untuk upload**;
karena akan menghalangi result AI Raspberry Pi.
Build kedua menggunakan source dari commit yang sama,
dengan `build_flags = -DENABLE_PI_RF30_RETURN=1`
pada salinan konfigurasi di direktori build terpisah.
PlatformIO: `atmelavr@5.1.0`,
`framework-arduino-avr@5.2.0`,
`avr-gcc 7.3.0`,
`ADS1X15@0.3.13`.

Hasil build kedua:

- `pio run -e mega2560`: **SUCCESS**.
- RAM: **3.917/8.192 byte (47,8%)**.
- Flash: **35.770/253.952 byte (14,1%)**.
- SHA256 build HEX:
  `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
- SHA256 HEX RF30 yang sebelumnya terbukti berhasil
  pada COM4: **sama persis**.
- Intel HEX keduanya dari alamat 0 sampai 35.769,
  **0 byte berbeda**. Dipakai HEX hasil compile
  `D:\ENOSE\_rf30_COM3_37095d0f\build\.pio\build\mega2560\firmware.hex`.
- File source commit dan checkout utama tetap tidak diubah.

## 2. Preflight COM3

`python -m serial.tools.list_ports -v`
menunjukkan COM3 FT232RL `A10KN6X9A`.
Windows PnP status OK.

`avrdude -p m2560 -c wiring -P COM3 -b 115200 -n -v`:
`Device signature = 0x1e9801` **PASS**.

Receiver `lcd_acquisition_service.py` yang masih hidup
secara khusus memilih **FTDI berbeda** `A10KNJBLA`,
tidak COM3. `data/raw/.incoming` kosong. Tidak ada
proses `avrdude` atau receiver lain yang diketahui
memakai COM3 saat preflight.

Skrip pengaman:
`scripts/com3_commit37095_guarded_deploy.py`
memeriksa serial USB, hash build, signature, backup
dan pemakaian serial sebelum penulisan.

## 3. Backup asli dari COM3 — sebelum upload

Lokasi **privat dan diabaikan Git**:

```text
private/com3_commit_37095d0f/
  backup_20261123_170216_096046/
    original_flash.hex
    original_eeprom.hex
    original_flash_full_262144.bin
    original_eeprom_full_4096.bin
    01_signature_readonly.log
    02_read_original_flash_and_eeprom.log
    03_suffix_terminal_readonly.log
    manifest.json
```

- Flash asli logis **262.144 byte**; EEPROM **4.096 byte**.
- Terminal AVRDUDE `dump flash` mengonfirmasi
  **738 byte suffix FF** secara fisik; tidak diasumsikan.
- SHA256 full Flash asli:
  `c2ba6f24d73665f8bb8ae53b3625680cb59adee0f47a36328072690bf7f6526d`.
- SHA256 EEPROM asli:
  `421df5f9fe52395b40b5dc90090eb0e7ba9f191c758ea87e551a1e01ba045402`.
- Backup checksum valid. Firmware lama tidak
  diberi label SVM atau RF tanpa bukti;
  kemampuan restore fisik belum dicoba.
- Tidak ada penulisan EEPROM, Flash atau fuse pada tahap backup.

## 4. Flash dan verifikasi

Setelah backup **`COM3_ORIGINAL_FLASH_EEPROM_VERIFIED`**,
operator sebelumnya sudah secara eksplisit meminta upload.
Prosedur yang dijalankan:

```powershell
python scripts/com3_commit37095_guarded_deploy.py --flash private/com3_commit_37095d0f/backup_20261123_170216_096046 --approval I_APPROVE_COM3_A10KN6X9A_COMMIT37095_RF30_FLASH_WITH_VERIFIED_BACKUP
```

Output privat:
`private/com3_commit_37095d0f/flash_20261123_170355_651391/`.

- COM3 dan signature MCU diperiksa lagi.
- AVRDUDE `-D -U flash:w:<exact-built-HEX>:i`
  **35.770 byte written PASS**.
- AVRDUDE terpisah
  `-n -U flash:v:<exact-built-HEX>:i`:
  **35.770 bytes of flash verified, PASS**.
- EEPROM dibaca ulang menggunakan
  `-n -U eeprom:r:...`, SHA256 sama dengan
  sebelum flash:
  **`421df5f9fe52395b40b5dc90090eb0e7ba9f191c758ea87e551a1e01ba045402`**.
- Tidak ada EEPROM/fuse/lockbit/TFT Nextion yang di-upload.
- Status manifest:
  `COM3_RF30_FLASH_VERIFY_AND_EEPROM_PRESERVATION_PASS_BOOT_PENDING`
  (status itu dicatat sebelum pemeriksaan boot).

## 5. Pemeriksaan boot UART dan masalah sensor I²C

Uji passive serial pertama gagal membuka COM3
(`Access is denied`) segera setelah flashing.
Tidak ada penulisan baru akibat kegagalan ini.
Pada percobaan berikutnya, port terbuka normal
dengan **satu pulse DTR reset selama 140 ms**.
Tanpa mengirim satu byte UART (`uart_tx_bytes=0`),
program menerima **1.181 byte** pesan boot.

```json
{
  "event": "FW_HELLO",
  "protocol": "legacy-json.v1",
  "build_id": "take30-ai30-rfhost-20261110",
  "adc_channels": 10,
  "data_cycles_total": 30,
  "ai_cycles_total": 30,
  "purge_s": 25,
  "collect_s": 5
}
```

Firmware juga melaporkan konfigurasi
Nextion `Serial2` @9600 baud, dan pesan
`Sistem siap` (pesan generik, **tidak boleh
dianggap sensor siap**).

**Masalah utama hasil boot:**

```text
ADS1115 #1 (0x48) tidak terdeteksi
ADS1115 #2 (0x49) tidak terdeteksi
ADS1115 #3 (0x4A) tidak terdeteksi
ADS1115 #4 (0x4B) tidak terdeteksi
ADS1115 terdeteksi: 0/4
SHT30 (0x44) tidak terdeteksi
Sensor init gagal. Periksa wiring (SDA=pin20, SCL=pin21).
```

Log UART:
`private/com3_commit_37095d0f/postflash_boot_20261123_170629_203109/`.
Karena semua sensor I²C absen, sebabnya
perlu diperiksa secara fisik: catu daya
board sensor, common GND, kabel SDA/SCL
Mega2560 pin 20/21, atau apakah COM3
adalah board ATmega tanpa sensor terpasang.
**Tidak ada scan I²C aktif, kalibrasi,
pengambilan data, kontrol pompa/valve
atau AI Test fisik pada sesi ini.**

## 6. Status akhir

| Tahap | Status |
|---|---|
| Source commit tepat `37095d0f` | PASS |
| Build dengan fitur return Pi, identik RF30 COM4 | PASS |
| Identitas FTDI COM3 + signature ATmega2560 | PASS |
| Backup Flash+EEPROM asli COM3 | PASS |
| Upload 35.770 byte | **PASS** |
| Verifikasi Flash independen | **PASS** |
| EEPROM tetap identik | **PASS** |
| `FW_HELLO` dari perangkat COM3 | **PASS** |
| ADS1115 dan SHT30 terdeteksi | **FAIL (0/4 dan absent)** |
| Tampilan fisik Nextion/menu utama | Belum diverifikasi |
| Take Data atau AI Test live | Belum dijalankan; **jangan mulai sebelum sensor pulih** |

**Kesimpulan:** permintaan build/flash/upload
commit `37095d0f` ke COM3 **berhasil**.
Pengoperasian penuh E-Nose tetap tertahan
karena sensor I²C tidak ditemukan di COM3.
