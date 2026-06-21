import pytest

from tidalist.metadata.rate_limit import MinInterval


def _clocked():
    clock = [0.0]
    slept = []

    def now():
        return clock[0]

    def sleep(s):
        slept.append(s)
        clock[0] += s

    return clock, slept, now, sleep


def test_first_call_does_not_sleep():
    clock, slept, now, sleep = _clocked()
    MinInterval(60, now=now, sleep=sleep).wait()
    assert slept == []


def test_immediate_second_call_sleeps_the_interval():
    clock, slept, now, sleep = _clocked()
    mi = MinInterval(60, now=now, sleep=sleep)  # 60/min -> 1.0s interval
    mi.wait()
    mi.wait()
    assert slept == [1.0]


def test_no_sleep_when_enough_time_elapsed():
    clock, slept, now, sleep = _clocked()
    mi = MinInterval(60, now=now, sleep=sleep)
    mi.wait()
    clock[0] = 2.0
    mi.wait()
    assert slept == []


def test_rejects_nonpositive_rate():
    with pytest.raises(ValueError):
        MinInterval(0)
