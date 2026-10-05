# Smart Coffee E-Nose v2

Firmware, antarmuka Nextion, akuisisi data, dan pipeline AI untuk sistem
e-nose berbasis **ATmega2560**.

## Hardware utama

- ATmega2560
- 10 kanal sensor gas melalui ADS1115
- SHT30 untuk temperatur/kelembapan
- pompa + valve
- Nextion NX4827T043_011
- Raspberry Pi 5 untuk integrasi/inferensi lanjutan

## Komunikasi serial

### USB/host

`Serial` menggunakan **115200 baud** untuk log, command, dan akuisisi data ke
PC/Raspberry Pi.

### Nextion

Nextion menggunakan **USART2 / `Serial2` pada 9600 baud**, sesuai konfigurasi
aktif file HMI.

| Jalur | ATmega2560 package | Arduino Mega header equivalent |
|---|---|---|
| Nextion TX -> MCU RX | PH0 / RXD2, physical pin 8 | RX2 / D17 |
| Nextion RX <- MCU TX | PH1 / TXD2, physical pin 9 | TX2 / D16 |
| Ground | GND | GND |

Catatan: **physical pin 8/9 pada IC ATmega2560 bukan Arduino digital D8/D9**.
PH0/PH1 adalah USART2, sehingga firmware harus memakai `Serial2`.

## Struktur repository

```text
.
├── src/                 firmware ATmega2560 utama
├── include/             header/model untuk firmware
├── lib/                 library embedded lokal
├── test/                smoke/unit test firmware
├── platformio.ini       konfigurasi PlatformIO
├── nextion/             source HMI, TFT, asset, event, dokumentasi
├── scripts/             akuisisi, validasi, feature engineering, training
├── data/
│   ├── raw/             data sensor mentah
│   ├── processed/       feature dataset dan dataset ML
│   └── analysis/        hasil validasi kualitas data
├── models/              model AI dan metadata fitur
├── results/
│   ├── plots/           plot analisis/model
│   └── sensor-plots/    plot detail tiap sampel/sensor
├── docs/                dokumentasi proyek
└── archive/             kode/eksperimen lama yang tidak lagi canonical
```

Firmware canonical hanya berada di `src/`. File lama dan eksperimen tidak
boleh dijadikan sumber implementasi produksi tanpa verifikasi.

## Build firmware

```powershell
pio run -e mega2560
```

Upload ke board:

```powershell
pio run -e mega2560 -t upload
```

Serial Monitor USB:

```powershell
pio device monitor -e mega2560
```

## Uji komunikasi Nextion

Environment `nextion_test` dipakai untuk mengisolasi komunikasi LCD dari
sensor/aktuator.

```powershell
pio run -e nextion_test
pio run -e nextion_test -t upload
pio device monitor -e nextion_test
```

Jika komunikasi benar, firmware test akan mengubah halaman Nextion dan event
sentuhan akan muncul sebagai `[NEXTION RX] EVT:...` pada Serial Monitor.

Firmware utama juga mencetak event yang diterima sebagai:

```text
{"nextion_event":"EVT:DATA_START"}
```

## Akuisisi data

Data baru dari `scripts/3_collect_data.py` disimpan ke `data/raw/`.
Kontrak akuisisi aktif mulai B32 adalah:

- 5 run;
- 25 detik purging + 5 detik collecting per run;
- 10 kanal gas menggunakan adc_mq3, bukan adc_mq9;
- temperature dan humidity SHT30 ikut disimpan di setiap row.

Validasi raw data aktif sengaja dibatasi ke B32:

    python scripts/validate_b32_acquisition.py

Raw data lama yang masih menggunakan MQ9 tidak dihapus. File tersebut
dipisahkan ke data/raw/legacy_mq9/ dan dikecualikan dari validasi B32.

Pada tahap kerja saat ini fokus project adalah akuisisi data. Jangan
menjalankan training model atau menganggap model lama sebagai model deployment
Raspberry Pi sebelum pipeline AI diperbarui secara terpisah.

### Akuisisi langsung dari LCD Nextion

Laptop dapat menjadi passive autosave host pada USB Serial COM5. Setelah
firmware terbaru terpasang, alurnya:

    pilih Roast / Origin / Batch di pTake
        -> tekan START di Nextion
        -> ATmega menjalankan 5 siklus
        -> COM5 mengirim raw JSON + metadata pilihan LCD
        -> scripts/lcd_acquisition_service.py menyimpan CSV ke data/raw/

Listener tidak mengirim command start ke ATmega. START tetap berasal dari LCD.
Service juga hanya menyimpan mode labeled_data; AI test tidak dimasukkan ke
dataset.

Install background listener + autostart Windows:

    powershell -ExecutionPolicy Bypass -File scripts/install_lcd_autosave.ps1

Cek status:

    powershell -ExecutionPolicy Bypass -File scripts/status_lcd_autosave.ps1

Stop dan lepaskan autostart:

    powershell -ExecutionPolicy Bypass -File scripts/uninstall_lcd_autosave.ps1

Saat listener aktif, COM5 bersifat eksklusif. Hentikan listener lebih dulu
sebelum memakai PlatformIO upload, Serial Monitor, atau 3_collect_data.py.

Data run aktif ditulis lebih dahulu ke data/raw/.incoming/. Setelah
ACQ_COMPLETE diterima, file dipindahkan menjadi CSV final. Run terputus
dipertahankan di data/raw/incomplete/ agar data tidak hilang diam-diam.

## Pipeline data/AI

- raw acquisition: `data/raw/`
- feature/ML dataset: `data/processed/`
- validation reports: `data/analysis/`
- trained models: `models/`
- evaluation and plots: `results/`

Jangan commit cache Python, virtual environment, atau build PlatformIO.
