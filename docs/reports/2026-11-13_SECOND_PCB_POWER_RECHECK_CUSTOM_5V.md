# Pemeriksaan ulang catu custom 5 V Raspberry Pi 5 — status idle dan batas diagnosis

**Tanggal:** 13 November 2026, 18.22–18.25 WIB

**Konteks:** kelanjutan laporan `2026-11-13_SECOND_PCB_POWER_STOP_CONDITION.md`
**Perangkat:** Raspberry Pi 5 yang terhubung ke FT232R PCB kedua; tidak melakukan diagnosis UART/MCU aktif.

## Konfirmasi operator

Operator memastikan Raspberry Pi memperoleh daya melalui **power supply 5 V dari rangkaian custom**, bukan adaptor USB-C bawaan. Pemeriksaan operator menunjukkan sekitar **5 V** dan indikator merah **tidak berkedip**. Lokasi titik ukur, rating arus maksimum PSU, dan kemampuan menjaga tegangan selama startup/beban berubah **belum diketahui**. Informasi operator tidak boleh diperlakukan sebagai hasil ukur langsung pada input Pi.

## Pemeriksaan host read-only

- SSH melalui Tailscale berhasil, tanpa perubahan pengaturan boot, service atau firmware.
- FT232R USB serial `A10KNJBL` masih terenumerasi dan by-id mengarah ke `/dev/ttyUSB0`; `fuser` tidak menemukan pemegang port.
- PMIC Raspberry Pi 5 melalui `vcgencmd pmic_read_adc EXT5V_V`: pembacaan awal **4,97140 V**.
- Temperatur melalui `vcgencmd measure_temp`: **36,7°C** saat sampel awal.
- Status `vcgencmd get_throttled` tetap **`0x50000`** selama delapan sampel, artinya **historis** bit undervoltage/throttling terjadi sejak boot; bit **aktif sekarang tidak menyala**.
- Journal kernel boot sebelumnya mengandung `Undervoltage detected!` pada **18.06.52** dan **18.07.09**, diikuti `Voltage normalised`. Tidak ada kejadian undervoltage baru yang terlihat pada bagian journal terakhir yang diperiksa.

### Delapan sampel tegangan saat idle

| Waktu lokal (WIB) | `EXT5V_V` | `get_throttled` |
|---|---:|---|
| 18.24.44 | 4,97408 V | `0x50000` |
| 18.24.47 | 4,93522 V | `0x50000` |
| 18.24.51 | 4,97140 V | `0x50000` |
| 18.24.54 | 4,97274 V | `0x50000` |
| 18.24.57 | 4,97408 V | `0x50000` |
| 18.25.01 | 4,97140 V | `0x50000` |
| 18.25.04 | 4,97140 V | `0x50000` |
| 18.25.08 | 4,96872 V | `0x50000` |

**Minimum 4,93522 V, maksimum 4,97408 V, rata-rata 4,96738 V**. Pengukuran dilakukan tanpa mengaktifkan beban baru. Pembacaan PMIC bersifat sesaat dan **tidak dapat menangkap semua transien singkat** maupun membuktikan kemampuan PSU ketika pompa/valve/sensor aktif.

Dokumentasi resmi Raspberry Pi:

- https://www.raspberrypi.com/documentation/computers/os.html — `pmic_read_adc EXT5V_V` pada Pi 5.
- https://www.raspberrypi.com/documentation/computers/raspberry-pi.html — peringatan undervoltage sekitar 4,63 V (dengan toleransi) dan kemungkinan efek PSU/kabel.

## Penilaian teknis

**PASS terbatas: tegangan input Pi pada kondisi idle saat dibaca berada di rentang 4,935–4,974 V**, temperatur tidak mengindikasikan panas abnormal, USB FT232R masih tersedia, dan tidak ada flag undervoltage **aktif** selama pembacaan.

**BELUM LULUS:** bukti stabilitas **startup** dan operasi pada beban penuh; riwayat undervoltage/throttling `0x50000` belum hilang karena berlaku untuk boot ini. Jangan menyimpulkan bahwa catu 5 V custom telah memenuhi kebutuhan arus/kabel Pi 5 hanya dari tegangan idle dan LED.

Kemungkinan penurunan sementara terjadi di kabel/konektor USB-C, saat inrush boot, atau ketika beban lain berubah. Ini **hipotesis**, bukan hasil pengukuran. Selain itu, undervoltage Pi **belum terbukti** menjadi penyebab layar Nextion tetap `Initializing Systems` karena PCB MCU/HMI dapat mempunyai jalur suplai berbeda.

## Batas tindakan berikutnya

1. **Perlu penjelasan operator:** titik ukur 5 V (output PSU atau terminal USB-C/input Pi ketika terhubung), rating maksimum arus PSU, dan apakah ada kapasitas beban simultan untuk Pi + PCB.
2. **Perlu inspeksi onsite dan izin khusus:** ukur tegangan di titik input Pi saat startup **dengan alat ukur dan metode aman**; periksa konektor, kabel dan apakah jalur USB dari PCB menyuplai balik 5 V. Hindari menghubungkan dua sumber 5 V sebelum sistem ground dan power path dikaji.
3. Setelah suplai dinyatakan stabil untuk startup dan operator setuju, lakukan observasi sistem **pasif**; jangan gunakan perubahan `get_throttled=0x50000` saja sebagai indikator kesalahan yang aktif sekarang. Evaluasi juga journal aktual pada boot yang dimonitor.
4. Akses RESET/ISP, upload RF30, pengujian sensor/pompa/valve dan inferensi RF500 live **tetap diblokir** hingga keamanan catu dan jalur firmware PCB kedua sudah diverifikasi.

**Tidak ada serial-open, MCU reset, EEPROM/Flash write, uji aktuator, uji beban, ataupun perubahan permanen Pi selama pemeriksaan ini.**
