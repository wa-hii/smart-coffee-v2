"""Offline tests for safe CSV recovery; no serial access or real data changes."""
from pathlib import Path
import tempfile

from recover_receiver_completed_csv import digest, recover
from test_acquisition_integrity import make_complete_run


def main():
    with tempfile.TemporaryDirectory() as root:
        src = Path(root) / 'old/data/raw'
        dst = Path(root) / 'new/data/raw'
        src.mkdir(parents=True)
        source = src / 'D-GAW_B99.csv'
        make_complete_run(30).to_csv(source, index=False)
        before = digest(source)
        (src/'unrelated.csv').write_text('bad CSV', encoding='utf-8')
        dry = recover(src, dst)
        assert dry['would_copy'] == [source.name] and not dst.exists()
        first = recover(src, dst, apply=True)
        assert len(first['copied']) == 1
        assert (dst/source.name).exists() and digest(dst/source.name) == before
        again = recover(src, dst, apply=True)
        assert again['identical_skipped'] == 1 and not again['copied']
        # Same name, different existing data: never overwrite existing bytes.
        (dst/source.name).write_bytes(b'original destination must survive')
        collision = recover(src, dst, apply=True)
        assert len(collision['copied']) == 1
        assert collision['copied'][0]['name'] == 'D-GAW_B99_RECOVERED_001.csv'
        assert (dst/source.name).read_bytes() == b'original destination must survive'
        assert digest(dst/'D-GAW_B99_RECOVERED_001.csv') == before
        assert digest(source) == before
        assert collision['invalid_skipped'] == 1
    print('RECOVER_COMPLETED_CSV_NO_CLOBBER_OFFLINE_PASS')


if __name__ == '__main__':
    main()
