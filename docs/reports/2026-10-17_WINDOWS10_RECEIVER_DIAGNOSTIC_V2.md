# Windows 10 Receiver — v2 diagnostik instalasi dan runtime

**Latar belakang:** pengguna melaporkan Smart Coffee Receiver error saat dijalankan pada laptop Windows 10, **tanpa menyertakan isi error/log**. Karena laptop Windows 10 bukan host yang dapat diakses oleh DevSpace, akar masalah sebenarnya **belum terkonfirmasi**.

## Audit paket lama

- `INSTALL_ON_THIS_LAPTOP.bat` semula membuat virtual environment, memasang requirements, dan langsung memulai `pythonw.exe` melalui `install_autostart.ps1` tanpa preflight terarah.
- Kesalahan akibat Python versi/arsitektur yang tidak cocok, import/dependency, izin write folder atau tidak ditemukannya COM dapat menjadi tidak terlihat saat berjalan melalui `pythonw.exe` tanpa console.
- Receiver tetap hanya menangkap data real-time setelah operator menjalankan Take Data dari LCD; ATmega tidak menyimpan CSV host dan tidak bisa menjalankan program Windows ketika USB ditancapkan tanpa instalasi penerima.

## Perubahan v2

- File baru `scripts/receiver_preflight.py` menguji Python >=3.10 dan arsitektur 64-bit, dependency `pyserial`, `numpy`, `pandas`, kelengkapan paket, kemampuan tulis `data/raw`, `data/baseline`, dan `logs`, serta daftar port USB. Pemeriksaan **tidak membuka COM dan tidak mengirim perintah ke alat**.
- Installer sekarang menjalankan preflight **sebelum** membuat shortcut Startup dan menjalankan listener background. Gagal pada preflight menghentikan instalasi dengan pesan error yang terlihat.
- `windows_receiver/DIAGNOSE_WINDOWS_10.bat` menampilkan hasil preflight dan beberapa baris status/log.
- `windows_receiver/START_RECEIVER_DEBUG.bat` menjalankan listener dalam console foreground agar error dapat disalin/difoto. Hanya gunakan jika perangkat IDLE, jangan menghentikan listener selama pengambilan data.
- ZIP baru `dist/Smart_Coffee_ENose_USB_Receiver_Windows_v2.zip` berisi 19 file. ZIP v1 sengaja dipertahankan agar pemakai lama tidak kehilangan akses file mereka.
- README Windows menyertakan troubleshooting Python, driver FT232R dan konflik port.

## QA dan batas

- `python scripts/receiver_preflight.py`: PASS pada host pengembangan Windows 11, Python 3.14.3 64-bit, dependency terinstal, folder writable, FT232R terdeteksi COM4.
- `python scripts/test_receiver_bundle.py`: PASS, ZIP diekstrak ke direktori sementara, impor dependency, preflight, dan verifikasi tidak berisi data mentah.
- `python scripts/test_usb_autodetect.py`: PASS (mock auto COM, koneksi/putus, deteksi device tunggal/multipel).
- **BELUM TERUJI**: installer dan auto-start sebenarnya pada Windows 10 laptop teman. Untuk menemukan penyebab spesifik, pengguna perlu menjalankan `DIAGNOSE_WINDOWS_10.bat` pada laptop itu dan mengirim pesan error atau tangkapan layarnya. Hindari membagikan identitas Windows yang tidak diperlukan.
- Firmware/EEPROM, Nextion HMI dan CSV tidak diubah oleh pekerjaan ini.
