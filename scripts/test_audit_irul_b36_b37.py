"""Integrity and fail-closed regression for B36/B37 deep quality audit."""
from __future__ import annotations

from audit_irul_b36_b37 import run


def main():
    files,cycles,summary=run()
    assert len(files)==32 and len(cycles)==32*5*10
    assert summary['canonical_pass']==27 and summary['canonical_hold']==5
    assert summary['baseline_controls']==2 and summary['coffee_ui_files']==30
    assert summary['files_missing_all_temp']==32
    assert summary['files_missing_all_humidity']==32
    assert summary['historical_sha_collisions']==0
    assert summary['blind_score_allowed'] is False
    assert summary['model_promotion_allowed'] is False
    assert files['source_sha256'].nunique()==32
    assert not files['eligible_for_independent_blind'].any()
    assert not cycles['relative_delta'].isna().any()
    assert files.loc[files.batch=='B37','canonical_valid'].all()
    assert files.loc[(files.batch=='B36')&(~files.canonical_valid),'file'].nunique()==5
    print('IRUL_B36_B37_DEEP_AUDIT_REGRESSION_PASS')


if __name__=='__main__':
    main()
