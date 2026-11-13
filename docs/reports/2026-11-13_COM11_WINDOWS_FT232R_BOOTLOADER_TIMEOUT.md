# PCB kedua — FT232R pindah ke Windows COM11, bootloader tetap timeout

**Tanggal:** Jumat, 13 November 2026 (WIB). **Branch:** `wahyu`.

## Konfigurasi terbaru

Operator menghubungkan USB dari PCB ATmega2560 kedua ke laptop Windows, sekarang terdeteksi pada **COM11** (bukan COM5 milik board SVM30 sebelumnya).

```text
1 ports found
COM11
    desc: USB Serial Port (COM11)
    hwid: USB VID:PID=0403:6001 SER=A10KNJBLA
```

Windows PnP `FTDIBUS\\VID_0403+PID_6001+A10KNJBLA\\0000`, status `OK`. Ini cocok dengan keluarga adaptor FT232R serial `A10KNJBL` yang sebelumnya terpasang di Raspberry Pi, dengan identitas serial Windows mengandung akhiran `A`. Enumerasi USB/COM **bukan** verifikasi komunikasi ke chip ATmega.

## Receiver akuisisi Windows

Sebelum uji programmer, ditemukan proses `pythonw.exe` PID **15160**, menjalankan `scripts/lcd_acquisition_service.py --port auto --baud 115200`. Status terakhir receiver `state=connected, port=COM11`; log menyatakan `CONNECTED COM11` pukul 14:12 WIB. Proses ini berpotensi memonopoli port.

- Folder `data/raw/.incoming/` dipastikan **kosong**.
- Log tidak menunjukkan akuisisi aktif ketika operasi dilakukan.
- Proses receiver **khusus PID 15160** dihentikan sebelum AVRDUDE membuka COM11.
- Sesudahnya, inventaris proses tidak menemukan receiver tersebut atau AVRDUDE tertinggal; data mentah, CSV, dan HMI tidak diubah.
- **Receiver belum dijalankan ulang** agar tidak membuka/mereset COM11 sewaktu programmer belum siap. Operator perlu mengetahui layanan autosave Windows sementara berhenti.

## Satu upaya identifikasi ATmega2560 pada COM11

Tool: `C:\\Users\\wahyu\\.platformio\\packages\\tool-avrdude\\avrdude.exe` (AVRDUDE 6.3) dengan `avrdude.conf` dari PlatformIO.

Perintah read-only:

```text
avrdude.exe -C avrdude.conf -p m2560 -c wiring -P COM11 -b 115200 -n -v
```

Hasil:

```text
Using Port       : COM11
Using Programmer : wiring
Overriding Baud Rate : 115200
avrdude.exe: stk500v2_ReceiveMessage(): timeout
avrdude.exe: stk500v2_ReceiveMessage(): timeout
avrdude.exe: stk500v2_ReceiveMessage(): timeout
Process exited with code 1
```

Percobaan selesai tanpa memperoleh **device signature**. Tidak ada perintah `-U flash:w`, `-U eeprom:w`, chip erase, fuse change, kalibrasi, perintah pompa/valve, atau upload HMI. **Firmware ATmega PCB kedua belum diubah.**

## Bukti lain dan keputusan

- Firmware RF30 bootguard sudah dipaketkan privat untuk PCB kedua, SHA256 `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
- Model RF500 tetap siap di Pi dan lolos pemeriksaan checksum offline.
- Inventaris `private/` Windows yang diperiksa hanya menunjukkan backup Flash/EEPROM COM5 **PCB lama** pada 11 November, bukan backup PCB kedua.
- Percobaan bootloader melalui FT232R pada Pi pada 12 November juga timeout. Perpindahan FT232R ke COM11 tidak memperbaiki protokol bootloader.

**Status: NO-GO untuk upload fisik RF30.** Windows sekarang mempunyai port COM11 tetapi bootloader ATmega2560 PCB kedua tidak memberi signature, sehingga belum terbukti ada jalur pemrograman.

Kondisi ini cocok dengan beberapa kemungkinan: DTR/RESET tidak tersambung sehingga bootloader tidak aktif, bootloader tidak tersedia/berbeda, jalur TX/RX/GND tidak sesuai, masalah catu/level, atau MCU tidak menjalankan startup. Hal-hal ini perlu inspeksi fisik dan **belum dapat dipastikan dari COM11**. Status Nextion terakhir diketahui tetap `Initializing Systems`.

**Jalur penyelesaian:** identifikasi koneksi FT232R–ATmega (Serial0 TX0/RX0, DTR/RESET, GND), lakukan reset bootloader yang sesuai dengan board atau gunakan programmer ISP melalui ICSP (MISO/MOSI/SCK/RESET/VCC/GND) yang terbukti membaca signature `0x1e9801`; lakukan backup **Flash+EEPROM asli PCB kedua** dan verifikasi rollback; setelah itu unggah RF30 sekali dengan verifikasi, lalu uji startup Nextion dan inferensi RF500 end-to-end.

USB COM11 terdeteksi **bukan** bukti firmware berhasil diunggah. Tanpa jalur pemrograman yang dapat menjawab signature, memaksa upload atau memilih baud/programmer secara acak tidak dapat diklaim sebagai penyelesaian.
