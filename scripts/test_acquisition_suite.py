"""QA entrypoint untuk canonical acquisition B32+.

Test suite lama (MQ9 / 10 run / durasi lama) dipertahankan di:
archive/legacy/scripts/test_acquisition_suite_pre_b32.py
"""

from test_acquisition_payload import main as payload_regression_main
from validate_acquisition import main as validation_main


def main() -> int:
    if payload_regression_main() != 0:
        return 1
    return validation_main()


if __name__ == "__main__":
    raise SystemExit(main())
