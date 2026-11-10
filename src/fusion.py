"""세 신호 융합과 평가 (research_design.md 7절). 임근영 담당

- 주 모형: L2 규제 로지스틱 회귀 → 종합 위험점수(확률)와 기업별 신호 기여도(계수 × 표준화값)
- 비교 기준: 신호별 단일 모형, 표준화 값 동일가중 평균
- 강건성 확인: 그래디언트 부스팅 + 순열 중요도
- 학습·검증은 시간 순서로 나눈다 (무작위 분할 금지). 모형 계수와 경보 기준점은 학습 기간 자료로만 정한다
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score


def time_split(df, train_years, test_years, by="연도"):
    """시간 순서 분할. 학습 연도가 검증 연도보다 모두 앞서는지 확인한다"""
    if max(train_years) >= min(test_years):
        raise ValueError("학습 기간이 검증 기간보다 앞서야 합니다")
    return df[df[by].isin(train_years)], df[df[by].isin(test_years)]


def fit_logit(train, features, label="사건", C=1.0):
    """L2 규제 로지스틱 회귀. 사건이 드물어 사건 쪽에 가중치를 준다(class_weight='balanced')"""
    model = LogisticRegression(penalty="l2", C=C, class_weight="balanced", max_iter=1000)
    model.fit(train[features].values, train[label].values)
    model.feature_names = list(features)
    return model


def risk_score(model, df):
    """종합 위험점수 = 사건 확률 (0~1)"""
    return pd.Series(model.predict_proba(df[model.feature_names].values)[:, 1], index=df.index, name="위험점수")


def contributions(model, df):
    """기업별 신호 기여도 = 계수 × 표준화값 (로그오즈 단위, 양수일수록 위험을 높인 신호).
    행 합 + 절편 = 위험점수의 로그오즈"""
    coef = pd.Series(model.coef_[0], index=model.feature_names)
    contrib = df[model.feature_names].mul(coef, axis=1)
    contrib["절편"] = model.intercept_[0]
    return contrib


def coefficients(model):
    """변수별 계수표 (크기순)"""
    c = pd.Series(model.coef_[0], index=model.feature_names, name="계수")
    return c.reindex(c.abs().sort_values(ascending=False).index)


def equal_weight(df, features):
    """비교 기준: 표준화 값의 단순 평균 (가중치 학습 없음)"""
    return df[features].mean(axis=1).rename("동일가중 점수")


def threshold_from_train(y_train, score_train, target_recall=None):
    """경보 기준점을 학습 기간에서 정한다. target_recall이 없으면 F1이 가장 큰 점수"""
    cand = np.unique(score_train)
    best, best_val = cand[0], -1
    for t in cand:
        pred = score_train >= t
        val = (-abs(recall_score(y_train, pred, zero_division=0) - target_recall)
               if target_recall is not None else f1_score(y_train, pred, zero_division=0))
        if val > best_val:
            best, best_val = t, val
    return best


def evaluate(y, score, threshold):
    """AUC, PR-AUC(정밀도-재현율 곡선 면적), 기준점에서의 정밀도·재현율·F1"""
    pred = score >= threshold
    return pd.Series({
        "AUC": roc_auc_score(y, score),
        "PR-AUC": average_precision_score(y, score),
        "정밀도": precision_score(y, pred, zero_division=0),
        "재현율": recall_score(y, pred, zero_division=0),
        "F1": f1_score(y, pred, zero_division=0),
        "사건 비율": float(np.mean(y)),
    })


def boosting_check(train, test, features, label="사건", seed=42):
    """강건성 확인: 그래디언트 부스팅의 검증 AUC와 변수별 순열 중요도"""
    model = HistGradientBoostingClassifier(class_weight="balanced", random_state=seed)
    model.fit(train[features].values, train[label].values)
    score = model.predict_proba(test[features].values)[:, 1]
    imp = permutation_importance(model, test[features].values, test[label].values,
                                 scoring="roc_auc", n_repeats=20, random_state=seed)
    importance = pd.Series(imp.importances_mean, index=features, name="순열 중요도").sort_values(ascending=False)
    return roc_auc_score(test[label], score), importance
