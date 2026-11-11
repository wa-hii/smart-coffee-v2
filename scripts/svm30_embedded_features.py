"""The exact 30 feature names/order in the supplied final_svm.joblib.

This is a feature CONTRACT, not a model. The C++ streaming implementation
must preserve NumPy population std (ddof=0), ordinary ADC (not baseline
subtracted), 25 purging + 5 collecting observations, 30 cycles.
"""
FEATURE_ORDER=(
    "tgs822_max_mean",
    "tgs822_purging_mean_mean",
    "tgs822_plateau_mean",
    "tgs822_mean_mean",
    "tgs822_early_mean",
    "tgs822_purging_min_mean",
    "tgs822_late_mean",
    "tgs822_AUC_mean",
    "tgs2602_rel_response_mean",
    "tgs816_purging_std_mean",
    "tgs2602_purging_slope_mean",
    "tgs816_std_mean",
    "tgs816_purging_slope_mean",
    "tgs816_delta_mean",
    "tgs2602_delta_mean",
    "tgs2602_slope_rise_mean",
    "tgs2602_purging_std_mean",
    "mq8_max_mean",
    "tgs2602_purging_std_std",
    "tgs2602_std_mean",
    "tgs816_delta_std",
    "tgs816_purging_std_std",
    "mq8_AUC_mean",
    "tgs2602_delta_std",
    "mq8_early_mean",
    "mq8_purging_mean_mean",
    "mq8_late_mean",
    "mq8_std_mean",
    "tgs816_global_range",
    "tgs822_slope_rise_std",
)
assert len(FEATURE_ORDER)==len(set(FEATURE_ORDER))==30
