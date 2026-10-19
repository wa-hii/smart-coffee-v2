"""Read-only smoke regression for grouping, SHA validation and t0 anchor."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from plot_valid_30_siklus_audit import (
    AUDIT, ADC_COLS, OUT, batch_groups, load_verified, roast_groups,
    x_seconds, y_sensor,
)


def main():
    records=load_verified()
    assert len(records)==38
    assert len(roast_groups(records))==6
    assert len(batch_groups(records))==11
    assert len(ADC_COLS)==10
    assert len({r['sha256'] for r in records})==38
    # 25th (last) purging sensor measurement is t0; first collecting is +1s.
    for r in records:
        df=r['data']
        idx=r['t0_index']
        assert idx==24
        assert df.loc[idx,'run_id']==1 and df.loc[idx,'phase']=='purging'
        assert df.loc[idx,'sample_idx']==25
        assert df.loc[idx+1,'phase']=='collecting'
        assert abs(x_seconds(r,True)[idx])<1e-6
        assert 0.75<x_seconds(r,True)[idx+1]<1.25
        for sensor in ADC_COLS:
            assert abs(y_sensor(r,sensor,True)[idx])<1e-6
    groups=roast_groups(records)
    assert {r['level'] for r in groups[('TOR','B63')]}=={'L','M','D'}
    assert {r['level'] for r in groups[('CAT','B62')]}=={'L','M'}
    batches=batch_groups(records)
    assert sum(r['batch']=='B62' for r in batches[('TEM','M')])==2
    print('VALID_38_INPUTS_GROUPING_6_ROAST_11_CROSSBATCH_T0_AT_PURGE25_PASS')


if __name__=='__main__':
    main()
