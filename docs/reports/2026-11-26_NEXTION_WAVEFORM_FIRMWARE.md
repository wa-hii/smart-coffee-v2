# Firmware UI waveform — 26 November 2026

## Cakupan
Firmware saja. HMI/TFT, perangkat fisik, dataset, dan listener Pi tidak
diubah. Profil lama mega2560 tetap kompatibel dengan HMI lama; profil
mega2560_waveform memilih kontrak UI baru; mega2560_waveform_rf30 memilih
kontrak baru dan mengaktifkan RF return gate untuk pengujian terawasi saja.
RF return gate default dan identitas protokol host tetap dipertahankan.

## Kontrak HMI berikutnya
Tambahkan native Waveform empat kanal sebagai komponen terakhir pada
pDataRun (page 3, id 11, x242 y81 w216 h79) dan pTestRun (page 6,
id 10, x28 y72 w425 h46). Nama usulan wSensor pada kedua halaman.
ID merupakan kontrak yang diturunkan dari HMI acuan COMPILE_READY,
bukan bukti HMI baru sudah dibuat. Verifikasi ID, tipe, kanal, dan ukuran
di Editor sebelum flash firmware/TFT. Pertahankan semua ID halaman.
Hapus mExit dan event-nya pada pHome; hapus komponen confidence, origin,
probability pada pResult, pertahankan tRoast, mSave, mHome.

Kanal visual: TGS822, TGS2602, TGS816, MQ8 (urutan subset SVM yang
telah ada, bukan ranking RF terbaru). Warna rencana cyan, kuning,
merah, biru. Scaling tetap terhadap full-scale positif ADS1115 32767,
output 0..78 atau 0..45 piksel. Nilai negatif/ADC tidak tersedia
menyebabkan frame visual dilewati. Tidak ada perubahan ADC mentah,
JSON host, 30 siklus, 25/5 detik, 1 Hz, pin, baud, EEPROM, atau model.
Frame 4 kanal dikirim atomik terhadap kapasitas FIFO UART; frame
visual boleh dilewati jika FIFO penuh. Reset waveform saat masuk
halaman/reboot LCD, tidak mengirim data saat pause/idle. AI status
periodik disebar ke slot UI 125 ms pada profil baru.

## QA dan deployment
Uji host: g++ -std=c++11 -Wall -Wextra -Werror -Itest/nextion_waveform_host -Isrc test/nextion_waveform_host/test.cpp src/nextion_transport.cpp -o .pio/nextion_waveform_host.exe
Jalankan .pio/nextion_waveform_host.exe. Uji ini mencakup scaling,
framing FF, buffer penuh, empat kanal dan reset grafik.
Build dengan pio run -e mega2560 -e mega2560_waveform -e mega2560_waveform_rf30 -e nextion_test.
Regresi: test_stage1_firmware_contract.py, test_rf30_firmware_result_contract.py,
test_acquisition_suite.py, test_stage7_bridge.py, verifier HMI lama.
Build bukan izin upload. HMI baru perlu diverifikasi dan dikompilasi
oleh Editor; uji fisik dan E2E belum dilakukan. Jangan flash kandidat
ke alat yang masih memakai TFT lama atau sedang akuisisi.
Status PI RF berarti mode host dipilih, bukan heartbeat online.
