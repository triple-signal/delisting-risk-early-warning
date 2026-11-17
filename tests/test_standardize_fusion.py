"""표준화(연도별 윈저화·z점수·결측 표시)와 융합 모형의 시간 순서 분할·기여도"""
import numpy as np
import pandas as pd
import pytest

from src.fusion import contributions, evaluate, fit_logit, time_split
from src.standardize import abnormal, align_direction, fill_missing, standardize, winsorize, zscore


def panel(seed=0):
    rng = np.random.default_rng(seed)
    n = 200
    return pd.DataFrame({"연도": np.repeat([2019, 2020], n // 2),
                         "x": rng.normal(size=n), "y": rng.normal(size=n)})


def test_align_direction_flips_sign():
    df = pd.DataFrame({"a": [1.0, -2.0]})
    assert align_direction(df, {"a": -1})["a"].tolist() == [-1.0, 2.0]


def test_winsorize_is_per_year():
    df = panel()
    df.loc[0, "x"] = 1000                    # 2019년 극단값
    out = winsorize(df, ["x"])
    assert out.loc[0, "x"] == pytest.approx(df[df["연도"] == 2019]["x"].quantile(0.99))
    assert out["x"].max() < 1000


def test_zscore_mean0_sd1_each_year():
    out = zscore(panel(), ["x"])
    g = out.groupby("연도")["x"]
    assert np.allclose(g.mean(), 0, atol=1e-12)
    assert np.allclose(g.std(), 1)


def test_zscore_keeps_missing_and_constant_year_is_zero():
    df = pd.DataFrame({"연도": [1, 1, 2, 2], "x": [5.0, np.nan, 3.0, 3.0]})
    out = zscore(df, ["x"])
    assert np.isnan(out.loc[1, "x"])
    assert out.loc[2, "x"] == 0 and out.loc[3, "x"] == 0


def test_fill_missing_adds_indicator():
    out = fill_missing(pd.DataFrame({"x": [1.0, np.nan]}), ["x"])
    assert out["x"].tolist() == [1.0, 0.0]
    assert out["x_결측"].tolist() == [0.0, 1.0]


def test_abnormal_residual_removes_size_effect():
    df = panel()
    df["y"] = 2 * df["x"] + 1 + np.where(df.index == 5, 3.0, 0.0)   # 한 기업만 3만큼 비정상
    res = abnormal(df, "y", ["x"])
    assert res.abs().idxmax() == 5


def test_standardize_pipeline_runs():
    df = panel()
    df.loc[3, "y"] = np.nan
    out = standardize(df, ["x", "y"], signs={"y": -1})
    assert "y_결측" in out and out["y"].isna().sum() == 0


def test_time_split_rejects_future_training():
    df = panel()
    with pytest.raises(ValueError):
        time_split(df, [2020], [2019])
    tr, te = time_split(df, [2019], [2020])
    assert set(tr["연도"]) == {2019} and set(te["연도"]) == {2020}


def test_contributions_sum_to_log_odds():
    df = panel()
    df["사건"] = (df["x"] + 0.5 * df["y"] > 1).astype(int)
    model = fit_logit(df, ["x", "y"])
    c = contributions(model, df)
    p = model.predict_proba(df[["x", "y"]].values)[:, 1]
    assert np.allclose(c.sum(axis=1), np.log(p / (1 - p)))


def test_evaluate_perfect_ranking():
    r = evaluate(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9]), 0.5)
    assert r["AUC"] == 1.0 and r["F1"] == 1.0
