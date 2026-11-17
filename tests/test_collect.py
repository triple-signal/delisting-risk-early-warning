"""전체 표본 수집 운영: 한도 오류 판별, 중복 실행 잠금, 네트워크 장애 시 종료"""
import os
import subprocess
import sys

import pandas as pd
import pytest
import requests

import src.collect as c


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """실제 data/ 대신 임시 폴더를 쓰고, 예약 작업 삭제·대기는 막는다"""
    for name in ("LOCK_PATH", "LOG_PATH", "FAIL_PATH", "INDEX_PATH"):
        monkeypatch.setattr(c, name, tmp_path / getattr(c, name).name)
    monkeypatch.setattr(c, "remove_scheduled_task", lambda: None)
    monkeypatch.setattr(c.time, "sleep", lambda s: None)
    monkeypatch.setattr(requests, "get", requests.get)      # Budget이 바꾼 requests.get을 테스트 뒤 복구
    return tmp_path


def finished_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


@pytest.mark.parametrize("msg, expected", [
    ("DART 오류 020: 요청 제한을 초과하였습니다", True),
    ('{"status": "020"}', True),
    ("원문 수집 오류 20200330000123: 파일 없음", False),   # 접수번호 안의 020은 한도 오류가 아님
])
def test_limit_error_detection(msg, expected):
    assert c._is_limit_error(Exception(msg)) == expected


def test_pid_alive():
    assert c._pid_alive(os.getpid())
    assert not c._pid_alive(finished_pid())


def test_lock_live_process_blocks(sandbox):
    c.LOCK_PATH.write_text(str(os.getpid()))
    assert not c.acquire_lock()
    assert c.LOCK_PATH.read_text() == str(os.getpid())


def test_dead_lock_removed(sandbox):
    c.LOCK_PATH.write_text(str(finished_pid()))
    assert c.acquire_lock()
    assert c.LOCK_PATH.read_text() == str(os.getpid())


def test_fresh_empty_lock_kept(sandbox):
    c.LOCK_PATH.write_text("")
    assert not c.acquire_lock()


def run_main(sandbox, monkeypatch, fail):
    c.INDEX_PATH.write_text("x")
    monkeypatch.setattr(c, "load_index", lambda: pd.DataFrame({"corp_code": ["A"] * 50, "사업연도": [2020] * 50}))
    monkeypatch.setattr(c, "tasks", lambda idx: [("원문", "A", 2020, str(n)) for n in range(50)])
    monkeypatch.setattr(c, "_done", lambda *a: False)
    calls = []

    def fake(*task):
        calls.append(task)
        if fail(len(calls)):
            raise requests.exceptions.ConnectionError("test")
    monkeypatch.setattr(c, "run_task", fake)
    monkeypatch.setattr(sys, "argv", ["collect"])
    return c.main(), len(calls)


def test_stops_after_consecutive_network_errors(sandbox, monkeypatch):
    rc, n = run_main(sandbox, monkeypatch, fail=lambda i: True)
    assert rc == 1 and n == c.MAX_NET_ERRORS
    assert not c.LOCK_PATH.exists()          # 잠금을 풀어 다음 예약 실행이 시작할 수 있음


def test_intermittent_errors_do_not_stop(sandbox, monkeypatch):
    rc, n = run_main(sandbox, monkeypatch, fail=lambda i: i % 5 != 0)
    assert rc is None and n == 50
    assert not c.LOCK_PATH.exists()
