# ARCHIEVE — versi lama, bukan rilis deployment

Nama `archieve` mengikuti permintaan pengguna. Folder `archive/` historis yang sudah ada tetap dipertahankan. Jangan flash dari folder ini tanpa audit dan izin rollback tersendiri.

- `legacy_source/firmware_629f4c15.zip`: source pra-Waveform, `firmware_e8d367e9.zip`: versi SVM30 standalone.
- `legacy_source/rf30_pre_waveform.hex`: kandidat RF30 lama (35.770 byte aplikasi).
- `legacy_source/listener_pre_waveform_629f4c15.zip`: snapshot skrip lama dari Git, bukan klaim seluruh runtime Pi lama identik.
- `legacy_source/supervisor_A10KN6X9.sh`: backup supervisor sebelum rebind A10KMZQJ, diambil dari Pi.
- `legacy_source/tracked_nextion_pre_v5.zip`: HMI historis dari Git. `local_nextion_versions/`: salinan HMI/TFT lokal lama (termasuk kandidat dan perubahan pengguna), tidak dipush. File yang terkunci dicatat dalam `fix/manifest.json` dan tetap ada di lokasi aslinya.
- `rf500_reference_not_validated/`: model lama dan metadata; klasifikasi lintas roasting belum lolos. Joblib lokal tidak dipublikasikan. SHA-256 tercatat dalam manifest.

Sumber build dan aset lama asli tidak dihapus/dipindah agar editor, skrip, Git history dan perubahan pengguna tetap aman. Ini adalah arsip salinan, bukan penghapusan file asli. Backup Flash/EEPROM board spesifik tetap di `private/`, bukan arsip firmware yang boleh dipasang ke board lain.
