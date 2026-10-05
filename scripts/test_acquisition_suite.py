"""Compatibility entrypoint untuk QA akuisisi aktif.

Test suite lama (MQ9 / 10 run / durasi lama) dipertahankan di:
archive/legacy/scripts/test_acquisition_suite_pre_b32.py

QA aktif sekarang sengaja hanya memvalidasi raw CSV B32.
"""

from validate_b32_acquisition import main


if __name__ == "__main__":
    raise SystemExit(main())
