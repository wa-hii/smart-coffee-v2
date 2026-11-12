# PCB kedua — Nextion tertahan pada Initializing Systems

Tanggal: 12 November 2026 (WIB). Branch: `wahyu`.

## Koreksi identitas sistem dari operator

- Operator menggunakan **SSH melalui Tailscale ke Raspberry Pi 5**, bukan lagi COM5 Windows.
- FT232R serial `A10KNJBL` pada Pi terhubung secara fisik ke **PCB ATmega2560 yang berbeda** dari alat yang menjalankan SVM30 standalone pada 11 November.
- Nextion pada PCB kedua sekarang tetap menampilkan **`Initializing Systems`**, sementara operator menyatakan alat berada pada kondisi **IDLE**.
- Karena alatnya berbeda, **jangan menyimpulkan SVM30 standalone terpasang pada PCB ini**. Image SVM30 dan backup Flash/EEPROM COM5 11 November hanya berlaku untuk **PCB lama**, bukan rollback PCB kedua.

## Preflight pasif Raspberry Pi dan FT232R

Pemeriksaan dilakukan melalui SSH tanpa membuka `/dev/ttyUSB0`, mengubah DTR/RTS, me-reset perangkat, mengendalikan pompa/valve, meng-upload firmware atau mengakses EEPROM.

| Pemeriksaan | Pengamatan |
|---|---|
| SSH | Berhasil, jam Pi sekitar 15:57:45 WIB |
| Uptime Pi | Sekitar 11 menit pada awal pemeriksaan |
| Catu Pi | `vcgencmd get_throttled=0x0` |
| USB | FT232R `A10KNJBL` -> `/dev/ttyUSB0` melalui `/dev/serial/by-id/` |
| Kernel | USB FTDI attached pada `3.964048` detik relatif boot; tidak ada `disconnect` pada journal boot yang diperiksa |
| Pemegang port | `fuser -v /dev/ttyUSB0` tidak menemukan pemilik |
| Layanan | `serial-getty@ttyUSB0` tidak aktif |
| Alat target | Versi firmware MCU, status firmware bootloader, jalur reset/DTR, I²C, dan UART2 **belum diketahui** |

Enumerator FT232R yang terlihat oleh Pi **bukan** bukti bahwa firmware MCU berjalan atau Nextion dapat menerima instruksi ATmega.

## Analisis source tanpa mengklaim kondisi firmware fisik

Pada `src/main.cpp` di repository saat ini:

1. `setup()` memulai `Serial` 115200, `Serial2` 9600 untuk Nextion, lalu `actuator.begin()`.
2. Profil host Pi melakukan `scanI2C()` terhadap alamat 1–126 dan `sensors.begin()` **sebelum** task scheduler diaktifkan. Jika inisialisasi bus terhambat, peralihan halaman juga tertunda. Ini **hipotesis**, bukan diagnosis pasti pada PCB kedua.
3. `serialCallback()` melakukan `nextion.poll()` dan memanggil `showNextionPage("pHome")` setelah sekitar 3000 ms apabila belum diarahkan ke halaman lain. Event `EVT:HMI_READY` juga dapat memulihkan halaman sesuai state akuisisi.
4. Karena Nextion tetap di halaman startup, kemungkinan meliputi MCU tidak menjalankan firmware yang cocok, proses startup terhambat, jalur Serial2/baud tidak cocok, HMI versi berbeda, atau suplai/perkabelan. Tidak ada bukti cukup untuk memilih salah satunya.
5. Raspberry Pi menjalankan inferensi hanya **setelah** perolehan 30 siklus; RF500/bridge Pi bukan penyebab yang dapat dipastikan dari gejala Nextion startup.

## Gerbang dan tindakan berikutnya

**Status:** FT232R host **PASS enumerasi pasif**, Nextion–MCU **BLOCKED/TIDAK TERDIAGNOSIS**, RF500 live **NO-GO**, flashing **NO-GO**.

Urutan aman:

1. Pastikan operator dapat memastikan suplai, tidak ada panas/bau abnormal, dan aktuator benar-benar dalam kondisi aman. Status IDLE yang dilaporkan tidak membuktikan tegangan rail aman.
2. Identifikasi metode komunikasi FT232R–ATmega2560 di PCB kedua termasuk TX/RX/GND, DTR/reset, bootloader dan apakah USB VBUS berpotensi backfeed. SSH tersedia tidak membuktikan bahwa jalur tersebut aman untuk flashing.
3. **Dengan izin tersendiri** untuk membuka serial yang dapat memicu reset, lakukan uji pasif berjangka pendek melalui FT232R dan catat marker `FW_HELLO` bila ada. Jangan memicu `#start`, `#scan`, atau kendali aktuator secara remote.
4. Jika akan mengganti firmware, lakukan **backup Flash dan EEPROM PCB kedua** lebih dahulu menggunakan programmer dan SOP daya/reset yang sudah dibuktikan; verifikasi signature, checksum dan rollback untuk **PCB kedua**. Jangan menggunakan dump/rollback PCB lama.
5. Baru sesudah identitas dan backup valid, tinjau apakah image firmware RF30 kandidat kompatibel dengan rangkaian PCB kedua; perbaiki masalah startup/HMI sebelum uji akuisisi 900 sampel atau aktivasi bridge live.

**Tidak ada flashing, perubahan HMI/EEPROM, pembacaan atau pengiriman byte serial, reset, maupun operasi aktuator dalam pemeriksaan ini.**
