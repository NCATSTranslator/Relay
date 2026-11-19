import gc

import pytest

from tr_sys import gc_tuning
from tr_sys.gc_tuning import DEFAULT_GC_THRESHOLD, apply_gc_threshold, parse_gc_threshold


@pytest.fixture
def restore_gc_threshold():
    before = gc.get_threshold()
    yield before
    gc.set_threshold(*before)


@pytest.mark.parametrize('value', [None, '', '   '])
def test_unset_or_empty_uses_default(value):
    assert parse_gc_threshold(value) == DEFAULT_GC_THRESHOLD


@pytest.mark.parametrize('value', ['off', 'OFF', ' Off ', 'false', 'none', 'default'])
def test_off_leaves_thresholds_alone(value):
    assert parse_gc_threshold(value) is None


@pytest.mark.parametrize('value, expected', [
    ('100000,50,100', (100000, 50, 100)),
    (' 50000 , 20 , 20 ', (50000, 20, 20)),
])
def test_explicit_thresholds(value, expected):
    assert parse_gc_threshold(value) == expected


@pytest.mark.parametrize('value', ['of', '100000', '100000,50', '1,2,3,4', '100000,50,x',
                                   '0,50,100', '-1,50,100', '1.5,50,100'])
def test_malformed_value_is_treated_as_off(value, caplog):
    with caplog.at_level('WARNING', logger=gc_tuning.logger.name):
        assert parse_gc_threshold(value) is None
    assert gc_tuning.ENV_VAR in caplog.text


def test_apply_sets_default_when_unset(monkeypatch, restore_gc_threshold):
    monkeypatch.delenv(gc_tuning.ENV_VAR, raising=False)
    assert apply_gc_threshold() == DEFAULT_GC_THRESHOLD
    assert gc.get_threshold() == DEFAULT_GC_THRESHOLD


def test_apply_sets_explicit_value(monkeypatch, restore_gc_threshold):
    monkeypatch.setenv(gc_tuning.ENV_VAR, '50000,20,20')
    assert apply_gc_threshold() == (50000, 20, 20)
    assert gc.get_threshold() == (50000, 20, 20)


@pytest.mark.parametrize('value', ['off', 'not-a-threshold'])
def test_apply_changes_nothing_when_off_or_malformed(monkeypatch, restore_gc_threshold, value):
    monkeypatch.setenv(gc_tuning.ENV_VAR, value)
    assert apply_gc_threshold() is None
    assert gc.get_threshold() == restore_gc_threshold