# Pi 5 RF500 rebind — 27 November 2026

Target: enose-v3@enose-pi5; currently attached FTDI A10KMZQJ -> /dev/ttyUSB0.
Supervisor had been waiting for A10KN6X9 and no Python listener owned the port.
With user approval, changed only the pinned FTDI path and associated wait log.
Verified bash syntax; preserved cron @reboot, singleton lock, model, bridge,
acquisition settings and dataset. Prior supervisor saved on Pi as
`rf500_pi_boot_supervisor.sh.bak_20261127_161019` in the always_on directory.
Stopped the old idle supervisor and sleep child, checked both locks released,
and started the replacement under the existing flock invocation.

16:10:20 WIB: RF500_PERSISTENT_READY, serial 115200, model_verified=true,
serial_open_once=true. Supervisor PID 2190; listener PID 2195 held ttyUSB0.
Startup recovered zero stale partials. Heartbeats at approximately 45-second
intervals reported 993 RX bytes, 17 frames, 12 non-JSON startup frames,
no active acquisition, no quarantine, no start rejections. Last prestart
event null: fresh FW_HELLO not yet verified. No second serial reader opened,
no forced MCU reset, no firmware/TFT flash. A controlled MCU-only reset while
idle with listener left open is needed to verify a fresh boot handshake.

Model, raw dataset and firmware were not modified. No reboot validation or
physical acquisition test was performed. Do not confuse heartbeat with
confirmation of a valid MCU hello or successful end-to-end AI inference.
