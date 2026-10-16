"""
Unit tests for the retry semantics of merge_and_post_process.

The DB, redis token gate and merge internals are all mocked out; these tests
exercise only the retry/backoff decision logic. Celery's eager mode re-executes
retries synchronously (Task.apply resubmits on Retry), so contention scenarios
run their full retry budget inline and we can assert exact attempt counts.
"""
from contextlib import nullcontext
from unittest.mock import patch, MagicMock

import pytest
from celery.exceptions import Retry, MaxRetriesExceededError

from tr_ars import utils
from tr_sys.celery_gates.expensive_gate import TASK_MAX_RETRIES


TASK_ARGS = ("parent-pk-1", {"knowledge_graph": {}}, "ara-test")


@pytest.fixture
def mock_parent():
    parent = MagicMock()
    parent.merge_semaphore = False
    parent.merged_versions_list = []
    return parent


@pytest.fixture
def merge_env(mock_parent):
    """Patch the DB, redis gate and merge internals; yield the mocks for per-test tuning."""
    merged = MagicMock()
    merged.id = "merged-pk-1"
    merged.pk = "merged-pk-1"
    env = {"parent": mock_parent, "merged": merged}
    with patch.object(utils, "transaction") as txn, \
         patch.object(utils, "get_object_or_404", return_value=mock_parent), \
         patch.object(utils, "Message") as message_cls, \
         patch.object(utils, "try_lock_merge", return_value=True) as try_lock, \
         patch.object(utils, "unlock_merge"), \
         patch.object(utils, "merge_received", return_value=(merged, mock_parent, {})) as merge_received, \
         patch.object(utils, "post_process", return_value=(merged, 200, "D")) as post_process, \
         patch.object(utils, "record_error"), \
         patch.object(utils, "exp_backoff_with_jitter", return_value=0), \
         patch.object(utils, "constant_backoff_with_jitter", return_value=0), \
         patch("tr_sys.celery_gates.context.try_acquire", return_value=True) as try_acquire, \
         patch("tr_sys.celery_gates.context.release") as release, \
         patch("tr_sys.celery_gates.context.LeaseRenewer"), \
         patch("tr_sys.celery_gates.context.constant_backoff_with_jitter", return_value=0):
        txn.atomic.return_value = nullcontext()
        message_cls.objects.filter.return_value.first.return_value = mock_parent
        message_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})  # never raised here
        env.update(try_lock=try_lock, try_acquire=try_acquire, release=release,
                   merge_received=merge_received, post_process=post_process)
        yield env


def _failed_events(mock_parent):
    return [c.args[0]["event_type"] for c in mock_parent.notify_subscribers.call_args_list
            if c.args[0].get("event_type") == "merged_version_failed"]


def test_happy_path_merges(merge_env):
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    merge_env["merge_received"].assert_called_once()
    merge_env["post_process"].assert_called_once()


def test_token_contention_retries_then_succeeds(merge_env):
    """A task that can't get a token keeps retrying and completes once one frees up."""
    merge_env["try_acquire"].side_effect = [False, False, False, True]
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    assert merge_env["try_acquire"].call_count == 4
    merge_env["merge_received"].assert_called_once()


def test_token_exhaustion_fails_loudly_after_full_budget(merge_env, mock_parent):
    """Budget exhaustion must fail (not silently return), after exactly the budgeted attempts."""
    merge_env["try_acquire"].return_value = False
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "FAILURE"
    assert isinstance(result.result, MaxRetriesExceededError)
    # initial attempt + TASK_MAX_RETRIES retries
    assert merge_env["try_acquire"].call_count == TASK_MAX_RETRIES + 1
    merge_env["merge_received"].assert_not_called()
    # the token was never held, so it must never be released
    merge_env["release"].assert_not_called()
    # exhaustion is surfaced to API consumers, not just logs
    assert _failed_events(mock_parent)


def test_lock_contention_releases_token_and_retries(merge_env):
    merge_env["try_lock"].side_effect = [False, False, True]
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    assert merge_env["try_lock"].call_count == 3
    # the expensive token must be released on each lock-contention requeue (and on success)
    assert merge_env["release"].call_count == 3


def test_lock_exhaustion_fails_loudly_after_full_budget(merge_env, mock_parent):
    merge_env["try_lock"].return_value = False
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "FAILURE"
    assert isinstance(result.result, MaxRetriesExceededError)
    assert merge_env["try_lock"].call_count == TASK_MAX_RETRIES + 1
    merge_env["merge_received"].assert_not_called()
    assert _failed_events(mock_parent)


def test_error_retries_stop_at_cap(merge_env):
    """A persistently failing merge is attempted exactly MERGE_ERROR_MAX_RETRIES + 1 times."""
    merge_env["merge_received"].side_effect = RuntimeError("boom")
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "FAILURE"
    assert isinstance(result.result, RuntimeError)
    assert merge_env["merge_received"].call_count == utils.MERGE_ERROR_MAX_RETRIES + 1


def test_error_retry_recovers_after_transient_failure(merge_env, mock_parent):
    merged = merge_env["merged"]
    merge_env["merge_received"].side_effect = [RuntimeError("boom"), RuntimeError("boom"),
                                               (merged, mock_parent, {})]
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    assert merge_env["merge_received"].call_count == 3


def test_error_retry_preserves_caller_kwargs(merge_env):
    """The error retry merges into request.kwargs instead of replacing them wholesale."""
    merge_env["merge_received"].side_effect = RuntimeError("boom")
    retry_spy = MagicMock(side_effect=Retry("requested retry"))
    kwargs = {"parent_pk": "parent-pk-1", "message_to_merge": {}, "agent_name": "ara-test"}
    with patch.object(utils.merge_and_post_process, "retry", retry_spy):
        result = utils.merge_and_post_process.apply(kwargs=kwargs)
    assert result.state == "RETRY"
    retry_kwargs = retry_spy.call_args.kwargs["kwargs"]
    assert retry_kwargs["error_retries"] == 1
    for key, value in kwargs.items():
        assert retry_kwargs[key] == value


def test_error_retry_increments_existing_counter(merge_env):
    merge_env["merge_received"].side_effect = RuntimeError("boom")
    retry_spy = MagicMock(side_effect=Retry("requested retry"))
    with patch.object(utils.merge_and_post_process, "retry", retry_spy):
        utils.merge_and_post_process.apply(
            kwargs={"parent_pk": "p", "message_to_merge": {}, "agent_name": "a",
                    "error_retries": 3})
    assert retry_spy.call_args.kwargs["kwargs"]["error_retries"] == 4


def test_direct_call_error_retry_survives_missing_request_kwargs(merge_env):
    """Called directly (not via a worker), request.kwargs is None; the retry must not TypeError."""
    merge_env["merge_received"].side_effect = RuntimeError("boom")
    retry_spy = MagicMock(side_effect=Retry("requested retry"))
    with patch.object(utils.merge_and_post_process, "retry", retry_spy):
        with pytest.raises(Retry):
            utils.merge_and_post_process(*TASK_ARGS)
    assert retry_spy.call_args.kwargs["kwargs"]["error_retries"] == 1