# Percobaan upload firmware RF30 melalui USB COM11 — berhenti sebelum penulisan

**Waktu:** 17 November 2026, sekitar 18.17–18.18 WIB.

## Target dan ruang lingkup

- **Target:** PCB E-Nose ATmega2560 SMD kedua via FT232RL onboard,
  USB VID:PID `0403:6001`, serial `A10KNJBLA`,
  terdeteksi sebagai `COM11` Windows.
- **Izin operator:** meminta langsung upload/flash firmware via
  USB laptop di COM11.
- **Kandidat:** RF30 Pi-return untuk PCB kedua,
  `private/rf30_second_pcb_candidate/20261112_rf30_bootguard_v1/rf30_pi_return_candidate.hex`,
  checksum SHA-256
  `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
  Payload Flash aplikasi 35.770 byte.
- **Programmer:** ArduinoISP pada Mega COM6 telah berhasil dipasang dalam
  sesi sebelumnya, tetapi **tidak ada sambungan fisik ISP ke PCB target**
  dan saat preflight ini hanya COM11 yang terdeteksi di Windows.

## Pengecekan host dan receiver

- Port COM11 dengan USB serial tepat teridentifikasi.
- Receiver `lcd_acquisition_service.py` (PID sebelumnya 25316)
  berjalan dan terhubung COM11. Folder `data/raw/.incoming`
  kosong; tidak ditemukan berkas akuisisi parsial di lokasi tersebut.
- Agar port tidak digunakan bersamaan, receiver lama dihentikan
  secara terarah setelah memverifikasi PID, command line dan
  direktori incoming kosong.
- Setelah uji, receiver berhasil dijalankan ulang sebagai
  **PID 14204** dan log mengonfirmasi `CONNECTED COM11`
  pada 18:18:31 WIB. Tidak ada perubahan CSV/HMI.

## Upload terjaga

Perintah yang dijalankan:

```text
python scripts/com11_rf30_verified_deploy.py --upload \
  --approval I_APPROVE_VERIFIED_COM11_SECOND_PCB_RF30_UPLOAD
```

Skrip tersebut menggunakan `avrdude.exe` dengan tahap pertama
read-only `-p m2560 -c wiring -P COM11 -b 115200 -n -v`,
timeout maksimum 20 detik.
Hasil hardware:

```text
Using Port : COM11
Using Programmer : wiring
Overriding Baud Rate : 115200
avrdude.exe: stk500v2_ReceiveMessage(): timeout
TIMEOUT_KILLED
state: BOOTLOADER_SIGNATURE_NOT_VERIFIED_NO_FLASH
return code: 3
flash_written: false
eeprom_written: false
backup_verified: false
firmware_uploaded: false
```

Raw log dan manifest (di-ignore dari Git):
`private/com11_second_pcb_deployment/20261117_181707_697517/`.

## Kesimpulan dan gerbang keselamatan

**Upload firmware E-Nose ke COM11 tidak berhasil dan tidak dilakukan.**
Perangkat USB FT232RL terdeteksi, tetapi bootloader ATmega target
tidak mengembalikan signature. Perintah backup dan Flash sengaja
tidak dicoba karena kriteria identitas belum lulus.

Alat tidak dipastikan rusak: penyebab bisa berupa bootloader tidak
tersedia, jalur UART0/RESET tidak benar-benar dapat diakses,
firmware fisik berbeda, atau masalah clock/reset/power MCU.
Pemindahan FT232RL USB ke Pi tidak otomatis memperbaiki
akses bootloader yang sama.

**Langkah fisik yang masih diperlukan:** akses ISP yang aman
melalui pad/testpoint/via PCB SMD atau pemeriksaan jalur
bootloader/reset dan catu MCU langsung pada PCB;
tanpa salah satunya tidak ada metode USB serial yang telah
terbukti mampu memprogram ATmega target.
Firmware RF30 tetap kandidat, model RF500 tetap belum live.
