"""Test cross-install singleton without opening any physical serial device."""
import os

from lcd_acquisition_service import (
    acquire_host_instance_lock,
    release_host_instance_lock,
)


def main():
    first = acquire_host_instance_lock()
    try:
        if os.name == 'nt':
            assert first is not None
            try:
                second = acquire_host_instance_lock()
            except RuntimeError as err:
                assert 'Receiver baru sudah berjalan' in str(err)
            else:
                release_host_instance_lock(second)
                raise AssertionError('Second receiver incorrectly obtained same host mutex')
        else:
            assert first is None
    finally:
        release_host_instance_lock(first)
    print('RECEIVER_CROSS_INSTALL_SINGLE_INSTANCE_OFFLINE_PASS')


if __name__ == '__main__':
    main()
