"""
Unit tests for the retry semantics of merge_and_post_process.

The DB and merge internals are all mocked out; these tests exercise only the
retry/backoff decision logic. Celery's eager mode re-executes retries
synchronously (Task.apply resubmits on Retry), so contention scenarios run
their full retry budget inline and we can assert exact attempt counts.
"""
from contextlib import nullcontext
from unittest.mock import patch, MagicMock

import pytest
from celery.exceptions import Retry, MaxRetriesExceededError

from tr_ars import utils
from tr_sys.celery_gates.backoff import MERGE_LOCK_MAX_RETRIES


TASK_ARGS = ("parent-pk-1", "child-pk-1", "ara-test")


@pytest.fixture
def mock_parent():
    parent = MagicMock()
    parent.merge_semaphore = False
    parent.merged_versions_list = []
    return parent


@pytest.fixture
def merge_env(mock_parent):
    """Patch the DB and merge internals; yield the mocks for per-test tuning."""
    merged = MagicMock()
    merged.id = "merged-pk-1"
    merged.pk = "merged-pk-1"
    # the child row the task loads its payload from, keyed by child_pk
    child = MagicMock()
    child.pk = "child-pk-1"
    child.decompress_dict.return_value = {"message": {"knowledge_graph": {}}}
    env = {"parent": mock_parent, "merged": merged, "child": child}
    with patch.object(utils, "transaction") as txn, \
         patch.object(utils, "get_object_or_404", return_value=mock_parent), \
         patch.object(utils, "Message") as message_cls, \
         patch.object(utils, "try_lock_merge", return_value=True) as try_lock, \
         patch.object(utils, "unlock_merge"), \
         patch.object(utils, "merge_received", return_value=(merged, mock_parent, {})) as merge_received, \
         patch.object(utils, "post_process", return_value=(merged, 200, "D")) as post_process, \
         patch.object(utils, "record_error"), \
         patch.object(utils, "exp_backoff_with_jitter", return_value=0), \
         patch.object(utils, "constant_backoff_with_jitter", return_value=0):
        txn.atomic.return_value = nullcontext()
        message_cls.objects.filter.return_value.first.return_value = mock_parent
        message_cls.objects.get.return_value = child
        message_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
        env.update(try_lock=try_lock, merge_received=merge_received,
                   post_process=post_process, message_cls=message_cls)
        yield env


def _failed_events(mock_parent):
    return [c.args[0]["event_type"] for c in mock_parent.notify_subscribers.call_args_list
            if c.args[0].get("event_type") == "merged_version_failed"]


def test_happy_path_merges(merge_env):
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    merge_env["merge_received"].assert_called_once()
    merge_env["post_process"].assert_called_once()


def test_lock_contention_retries_then_succeeds(merge_env):
    merge_env["try_lock"].side_effect = [False, False, True]
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    assert merge_env["try_lock"].call_count == 3
    merge_env["merge_received"].assert_called_once()


def test_lock_exhaustion_fails_loudly_after_full_budget(merge_env, mock_parent):
    """Budget exhaustion must fail (not silently return), after exactly the budgeted attempts."""
    merge_env["try_lock"].return_value = False
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "FAILURE"
    assert isinstance(result.result, MaxRetriesExceededError)
    # initial attempt + MERGE_LOCK_MAX_RETRIES retries
    assert merge_env["try_lock"].call_count == MERGE_LOCK_MAX_RETRIES + 1
    merge_env["merge_received"].assert_not_called()
    # exhaustion is surfaced to API consumers, not just logs
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
    kwargs = {"parent_pk": "parent-pk-1", "child_pk": "child-pk-1", "agent_name": "ara-test"}
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
            kwargs={"parent_pk": "p", "child_pk": "c", "agent_name": "a",
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


def test_payload_is_loaded_from_child_pk_not_the_task_args(merge_env):
    """The task takes a pk and reads the body from the DB, not from the celery payload."""
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    merge_env["message_cls"].objects.get.assert_called_once_with(pk="child-pk-1")
    merge_env["child"].decompress_dict.assert_called_once()
    # merge_received gets the inner "message", matching what callers used to pass inline
    passed = merge_env["merge_received"].call_args.args[1]
    assert passed == {"knowledge_graph": {}}


def test_missing_child_is_not_retried(merge_env):
    """A child row that no longer exists is permanent; retrying cannot fix it."""
    merge_env["message_cls"].objects.get.side_effect = merge_env["message_cls"].DoesNotExist
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"  # returns cleanly rather than erroring
    merge_env["merge_received"].assert_not_called()


def test_child_without_message_key_is_skipped(merge_env):
    merge_env["child"].decompress_dict.return_value = {"nothing": "here"}
    result = utils.merge_and_post_process.apply(args=TASK_ARGS)
    assert result.state == "SUCCESS"
    merge_env["merge_received"].assert_not_called()