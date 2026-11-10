"""신호 표준화 (research_design.md 7절 · 표준화 규칙). 임근영 담당

순서: ① 방향 통일 → ② (감사시간·보수) 규모·업종 효과 제거 → ③ 연도별 극단값 처리 → ④ 연도별 z점수
- 0/1 변수는 그대로 둔다
- 결측은 0(=그해 평균)으로 채우고 '결측' 0/1 열을 따로 만든다
- ③④의 기준값은 같은 사업연도 기업들의 값으로 정한다 (라벨을 쓰지 않으므로 미래 정보 누출 아님)
"""
import numpy as np
import pandas as pd

WINSOR = (0.01, 0.99)   # [구현] 상하위 1% 윈저화


def align_direction(df, signs):
    """① 방향 통일: signs = {열: +1 또는 -1}. -1이면 부호를 바꿔 '클수록 위험'으로 맞춘다.
    방향이 불분명한 변수는 signs에 넣지 않는다 (그대로 둠)"""
    out = df.copy()
    for col, s in signs.items():
        out[col] = out[col] * s
    return out


def abnormal(df, y, xs, by="연도", dummies=()):
    """② 비정상값: 그룹(연도)별로 y를 xs(+범주형 dummies)에 회귀한 잔차.
    예) 비정상 감사시간 = ln(감사시간) ~ ln(자산총계) + 업종 + 연결 여부 의 잔차.
    관측치가 설명변수 수 + 5개 미만인 그룹은 계산하지 않는다 (NaN)"""
    res = pd.Series(np.nan, index=df.index, name=f"{y}_비정상")
    for _, g in df.groupby(by):
        X = g[list(xs)].astype(float)
        if dummies:
            X = pd.concat([X, pd.get_dummies(g[list(dummies)].astype(str), drop_first=True, dtype=float)], axis=1)
        X.insert(0, "상수", 1.0)
        ok = X.notna().all(axis=1) & g[y].notna()
        if ok.sum() < X.shape[1] + 5:
            continue
        beta, *_ = np.linalg.lstsq(X[ok].values, g.loc[ok, y].values.astype(float), rcond=None)
        res.loc[ok[ok].index] = g.loc[ok, y].values - X[ok].values @ beta
    return res


def winsorize(df, cols, by="연도", limits=WINSOR):
    """③ 연도별 극단값 처리: 그해 상하위 limits 분위수 밖의 값을 경계값으로 바꾼다"""
    out = df.copy()
    for col in cols:
        lo = out.groupby(by)[col].transform(lambda s: s.quantile(limits[0]))
        hi = out.groupby(by)[col].transform(lambda s: s.quantile(limits[1]))
        out[col] = out[col].clip(lower=lo, upper=hi)
    return out


def zscore(df, cols, by="연도"):
    """④ 연도별 z점수: (값 − 그해 평균) / 그해 표준편차. 표준편차 0이면 0"""
    out = df.copy()
    for col in cols:
        g = out.groupby(by)[col]
        sd = g.transform("std").replace(0, np.nan)
        out[col] = ((out[col] - g.transform("mean")) / sd).fillna(0).where(out[col].notna())
    return out


def fill_missing(df, cols):
    """결측을 0으로 채우고 '열_결측' 0/1 열을 추가 (결측 자체가 신호일 수 있음)"""
    out = df.copy()
    for col in cols:
        miss = out[col].isna()
        if miss.any():
            out[f"{col}_결측"] = miss.astype(float)
        out[col] = out[col].fillna(0)
    return out


def standardize(df, continuous, binary=(), signs=None, by="연도"):
    """①③④ + 결측 처리를 한 번에. ②(abnormal)는 필요한 변수에 대해 먼저 따로 계산해 열로 넣는다.
    반환: 표준화된 표 (식별 열·라벨 열은 그대로 유지)"""
    out = align_direction(df, signs or {})
    out = winsorize(out, continuous, by=by)
    out = zscore(out, continuous, by=by)
    return fill_missing(out, list(continuous) + list(binary))
