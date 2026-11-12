"""데이터랩 공통 로직 단위 테스트.

API 를 호출하지 않는다. 재정규화와 배치 구성은 틀려도 에러 없이 숫자만 조용히
틀어지는 부분이라, 바꿀 때마다 이 테스트로 성질을 확인한다.

    python -m pytest -q
"""
import math

import pandas as pd
import pytest

from src.collect._common import _error_detail
from src.collect._datalab import add_rescaled, chunk_with_anchor


# ── 배치 구성 ─────────────────────────────────────────────
def test_anchor_is_first_slot_of_every_batch():
    batches = chunk_with_anchor(list("abcdefg"), "A", slots=3)
    assert all(b[0] == "A" for b in batches)
    assert all(len(b) <= 3 for b in batches)
    assert [x for b in batches for x in b[1:]] == list("abcdefg")


def test_anchor_duplicate_in_items_is_removed():
    batches = chunk_with_anchor(["반팔티", "패딩", "우산"], "반팔티", slots=5)
    assert batches == [["반팔티", "패딩", "우산"]]


def test_anchor_only_still_requests_once():
    assert chunk_with_anchor([], "A", slots=3) == [["A"]]


def test_slots_must_leave_room_for_anchor():
    with pytest.raises(ValueError):
        chunk_with_anchor(["a"], "A", slots=1)


# ── 앵커 재정규화 ─────────────────────────────────────────
def _frame(rows):
    return pd.DataFrame(rows, columns=["batch_id", "date", "ratio", "is_anchor"])


def test_anchor_rescaled_is_exactly_one_and_others_are_ratios():
    df = add_rescaled(_frame([
        ("b1", "2026-07-01", 80.0, True),
        ("b1", "2026-07-01", 40.0, False),
        ("b2", "2026-07-01", 50.0, True),   # 다른 배치: 분모가 다르다
        ("b2", "2026-07-01", 25.0, False),
    ]))
    assert df.loc[df.is_anchor, "rescaled"].tolist() == [1.0, 1.0]
    assert df.loc[~df.is_anchor, "rescaled"].tolist() == [0.5, 0.5]


def test_zero_or_missing_anchor_gives_nan_not_inf():
    df = add_rescaled(_frame([
        ("b1", "2026-07-01", 0.0, True),
        ("b1", "2026-07-01", 10.0, False),
        ("b1", "2026-07-02", 10.0, False),  # 이 날은 앵커 행이 없다
    ]))
    assert all(math.isnan(v) for v in df["rescaled"])


def test_duplicate_anchor_rows_are_rejected():
    with pytest.raises(ValueError):
        add_rescaled(_frame([
            ("b1", "2026-07-01", 80.0, True),
            ("b1", "2026-07-01", 70.0, True),
        ]))


# ── HUB 오류 본문 파싱 ────────────────────────────────────
class _Resp:
    def __init__(self, payload=None, text=""):
        self._p, self.text = payload, text

    def json(self):
        if self._p is None:
            raise ValueError
        return self._p


@pytest.mark.parametrize("payload,expected", [
    ({"error": {"errorCode": "200", "message": "Authentication Failed"}}, "gateway 200"),
    ({"errMsg": "Invalid parameter", "errId": "400"}, "[400] Invalid parameter"),
])
def test_error_detail_handles_both_hub_error_shapes(payload, expected):
    assert expected in _error_detail(_Resp(payload))


def test_error_detail_falls_back_to_text():
    assert _error_detail(_Resp(None, "<html> bad </html>")) == "<html> bad </html>"
