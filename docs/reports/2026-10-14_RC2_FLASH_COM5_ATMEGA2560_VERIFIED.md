# Flashing firmware RC2 ke custom PCB ATmega2560 — verified COM5

**Tanggal / waktu:** 14 Oktober 2026 sekitar 17:22–17:28 WIB.
**Eksekusi:** Windows via MCP_WAHYU DevSpace, perintah langsung setelah
izin eksplisit operator. **Status:** `FLASH_RC2_PASS; EEPROM_PRESERVED`.

## Target dan provenance

- Source `git HEAD=910bfc2`, tag
  `pre-onsite-software-2026-10-14-rc2`.
- Lokasi project Windows:
  `D:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware`.
- `pio device list`: **COM5**, FTDI USB serial `VID:PID=0403:6001`,
  serial Windows `A10KMM3SA` (Pi sebelumnya `A10KMM3S`).
  Windows PnP COM5 **OK**.
- Board PIO `megaatmega2560` (16 MHz); bootloader protocol
  `wiring` @ **115200 baud**.
- Chip signature dibaca via AVRDUDE: **`0x1E9801`**, cocok ATmega2560.
- Firmware `.pio/build/mega2560/firmware.hex` dibangun dari RC2
  dan diverifikasi SHA256
  `25c92c6a9ae4090e116807bb71566823e2c833be85596f5ea8a5fc829a13a453`.
- Tidak memakai build `nextion_test`, tidak menyentuh project HMI/TFT.

## Penanganan akses COM5 dan backup

Percobaan pertama read-only AVRDUDE gagal `Access is denied`.
Pemeriksaan proses mengidentifikasi Windows listener
`pythonw.exe ... lcd_acquisition_service.py --port COM5 --baud 115200`
PID 11144 yang memegang COM5. Status listener `connected`, tidak
ada `.partial.csv` aktif di `data/raw/.incoming/`. Proses tepat ini
dihentikan untuk melepaskan port sebelum melakukan flashing;
**layanan tidak otomatis di-restart** pada akhir tindakan.

Backup melalui `avrdude -p atmega2560 -c wiring -P COM5 -b 115200 -n`
berhasil membaca *flash* dan *EEPROM* sebelum upload. File fisik
backup **hanya tersimpan lokal** di:

`results/firmware-backup-20261014/`

| Backup | Ukuran file Intel HEX | SHA256 |
|---|---:|---|
| `pre_rc2_flash.hex` | 629073 byte | `5a130be3bc1c0bf4fd3472789c009c1fee90d066d7467eedc9024e2006b0e18a` |
| `pre_rc2_eeprom.hex` | 9869 byte | `749d6c5592faaac64b38d6491fd84dd0b38350ea81d30a229ad8b457572ce25c` |

Kedua Intel HEX memiliki EOF record yang benar. Backup merupakan
**readback melalui bootloader**, bukan dump ISP dengan pemeriksaan
bootloader/fuse/lockbit independen. Operasi pemulihan harus diawasi
operator dan diperiksa sebelum dijalankan; backup tidak di-upload
ke GitHub serta diabaikan oleh `.gitignore`.

## Flash & verifikasi

Perintah:

```powershell
pio run -e mega2560 -t upload --upload-port COM5
```

Output AVRDUDE:

```text
Device signature = 0x1e9801 (probably m2560)
avrdude: writing flash (34930 bytes)
avrdude: 34930 bytes of flash written
avrdude: verifying flash memory against .pio\build\mega2560\firmware.hex
avrdude: 34930 bytes of flash verified
avrdude done.  Thank you.
mega2560 SUCCESS
```

Setelahnya EEPROM diverifikasi terhadap backup sebelumnya:

```powershell
avrdude -p atmega2560 -c wiring -P COM5 -b 115200 -n `
  -U eeprom:v:results/firmware-backup-20261014/pre_rc2_eeprom.hex:i
```

Output: **`4096 bytes of eeprom verified`**, exit code 0.
Artinya seluruh byte EEPROM yang dibaca cocok dengan kondisi
sebelum flashing; tidak mengklaim kualitas atau validitas isi
kalibrasi EEPROM.

## Batas verifikasi dan tindakan selanjutnya

- Firmware RC2 **berhasil ditulis dan dibandingkan dengan flash
  chip via bootloader**, bukan sekadar build source.
- `FW_HELLO`/`ACQ_START.fw_build_id=g3-rc2-20261014` **belum**
  diuji ulang pada stream firmware runtime setelah flash.
- LCD Nextion dan pompa/valve **tidak** diuji selama prosedur upload.
  Pengujian lima siklus G3 **belum diulang** memakai RC2.
- Model inferensi tetap **NO_GO / `N/A`**, tidak ada prediksi roast,
  origin, maupun probabilitas yang boleh diklaim.
- Windows listener `lcd_acquisition_service.py` tetap **stopped**;
  jangan menjalankannya bersamaan dengan listener Raspberry Pi pada
  port USB yang sama.
- Pastikan PCB IDLE dan pengawasan di lokasi sebelum memindahkan
  kabel USB data kembali ke Pi sesuai SOP kelistrikan. Lakukan
  passive enumerasi Pi, G2, dan satu G3 terawasi dengan output
  listener `G3_LISTENER_READY_USB_RX_ONLY` sebelum operator menekan
  START AI TEST satu kali. Kumpulkan terminal `ACQ_COMPLETE` dan
  perbandingan build ID; jangan anggap lima siklus HMI saja cukup.
