# Evidence UART bench — Mega 2560 testbed ↔ Pi 5

**12 Oktober 2026, hardware fisik sudah diakses.**
Output JSON Pi diperoleh melalui SSH; tidak menggunakan
simulasi untuk menggantikan hasil fisik.

- `uart_rx_run01.json`: Pi GPIO15 UART0 9600 menerima
  **0 heartbeat dalam 20 detik** — FAIL/INCONCLUSIVE.
- `uart_tx_probe_run01.json`: Pi mengirim **satu PING**
  aman (dengan `--ping --probe-tx`); Pi menerima
  **0 heartbeat, 0 PONG**. USB Serial Mega pada
  saat yang sama mencetak HEARTBEAT 1–19 dan
  **0 baris PING ACK**.
- COM6 (Windows): USB-SERIAL CH340 VID:PID 1A86:7523;
  avrdude memverifikasi MCU signature **0x1e9801**
  (ATmega2560), flash/verify sketch bench **SUCCESS**.
- Raspberry Pi: `dtparam=uart0=on`,
  `dtoverlay=uart0-pi5`, GPIO14 TXD0,
  GPIO15 RXD0, `/dev/ttyAMA0`,
  serial-getty **inactive**, user dalam
  `dialout`, **no owner**, power `throttled=0x0`.
  Ini membuktikan konfigurasi UART aktif,
  **bukan** bahwa tegangan/gelombang sinyal
  sesuai.

**Kesimpulan:** firmware testbed berjalan,
tetapi jalur GPIO↔level shifter↔Mega belum
berfungsi dua arah. Wiring harus diperiksa
secara fisik oleh operator setelah mematikan
daya kedua perangkat. Jangan mengganti baud
acak, menyalakan aktuator, atau mengklaim
hardware-E2E PASS.

Full report: `bench/mega_pi_uart/reports/2026-10-12_BENCH_TEST.md`.
