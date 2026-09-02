"""
Unit tests for ingest_ara_response, the celery task that now does everything the
ARA-callback view used to do after receiving the body (parse, result count,
pre_merge_process, validation, notifications, enqueueing the merge).

DB, notifications and the merge internals are mocked; transaction.on_commit is
patched to run its callback immediately so the merge enqueue can be asserted.
"""
from unittest.mock import patch, MagicMock

import pytest

from tr_ars import tasks
from tr_ars import utils
from tr_ars.models import Message


CHILD_PK = "child-pk-1"
PARENT_PK = "parent-pk-1"


def _message(results, agent_name="ara-shepherd-test", params=None):
    mesg = MagicMock()
    mesg.pk = CHILD_PK
    mesg.ref_id = PARENT_PK
    mesg.actor_id = 7
    mesg.params = params if params is not None else {}
    mesg.updated_at = "2026-09-02T00:00:00"
    body = {"message": {"results": results, "knowledge_graph": {}}} if results is not None \
        else {"message": {}}
    mesg.decompress_dict.return_value = body
    return mesg


@pytest.fixture
def env():
    parent = MagicMock()
    actor = MagicMock()
    actor.inforesid = "infores:shepherd-test"
    actor.agent.name = "ara-shepherd-test"
    with patch.object(tasks, "Message") as message_cls, \
         patch.object(tasks, "Actor") as actor_cls, \
         patch.object(tasks, "get_object_or_404", return_value=parent), \
         patch.object(tasks, "transaction") as txn, \
         patch.object(utils, "pre_merge_process") as pre_merge, \
         patch.object(utils, "remove_phantom_support_graphs"), \
         patch.object(utils, "validate", return_value=True) as validate, \
         patch.object(utils, "ScoreStatCalc", return_value={"stat": 1}), \
         patch.object(utils.merge_and_post_process, "apply_async") as merge_enqueue:
        actor_cls.objects.get.return_value = actor
        # run on_commit callbacks immediately so the enqueue is observable
        txn.on_commit.side_effect = lambda fn: fn()
        yield {"message_cls": message_cls, "actor": actor, "parent": parent,
               "pre_merge": pre_merge, "validate": validate, "merge_enqueue": merge_enqueue}


def _events(parent):
    return [c.args[0]["event_type"] for c in parent.notify_subscribers.call_args_list]


def test_results_are_processed_and_merge_is_enqueued(env):
    mesg = _message(results=[{"a": 1}, {"b": 2}])
    env["message_cls"].objects.get.return_value = mesg

    result = tasks.ingest_ara_response.apply(args=(CHILD_PK, "D"))

    assert result.state == "SUCCESS"
    assert _events(env["parent"]) == ["ara_response_complete"]
    complete = env["parent"].notify_subscribers.call_args_list[0].args[0]
    assert complete["ara_n_results"] == 2
    assert complete["child_uuid"] == CHILD_PK
    assert mesg.result_count == 2
    assert mesg.status == "D"
    assert mesg.code == 200
    env["pre_merge"].assert_called_once()
    # the processed body is persisted before the merge task is enqueued
    mesg.save_compressed_dict.assert_called_once()
    env["merge_enqueue"].assert_called_once_with((PARENT_PK, CHILD_PK, "ara-shepherd-test"))


def test_status_header_is_applied(env):
    mesg = _message(results=[{"a": 1}])
    env["message_cls"].objects.get.return_value = mesg
    tasks.ingest_ara_response.apply(args=(CHILD_PK, "S"))
    assert mesg.status == "S"
    complete = env["parent"].notify_subscribers.call_args_list[0].args[0]
    assert complete["ara_response_status"] == "S"


def test_invalid_response_is_marked_422_and_not_merged(env):
    mesg = _message(results=[{"a": 1}])
    env["message_cls"].objects.get.return_value = mesg
    env["validate"].return_value = False

    result = tasks.ingest_ara_response.apply(args=(CHILD_PK, "D"))

    assert result.state == "SUCCESS"
    assert mesg.status == "E"
    assert mesg.code == 422
    assert _events(env["parent"]) == ["ara_response_complete", "ara_failed_validation"]
    env["merge_enqueue"].assert_not_called()


def test_validation_is_skipped_when_params_disable_it(env):
    mesg = _message(results=[{"a": 1}], params={"validate": False})
    env["message_cls"].objects.get.return_value = mesg
    env["validate"].return_value = False  # would fail if consulted
    tasks.ingest_ara_response.apply(args=(CHILD_PK, "D"))
    env["validate"].assert_not_called()
    env["merge_enqueue"].assert_called_once()


def test_no_results_records_zero_and_does_not_merge(env):
    mesg = _message(results=None)
    env["message_cls"].objects.get.return_value = mesg

    tasks.ingest_ara_response.apply(args=(CHILD_PK, "D"))

    assert mesg.result_count == 0
    assert mesg.status == "D"
    complete = env["parent"].notify_subscribers.call_args_list[0].args[0]
    assert complete["ara_n_results"] is None
    env["pre_merge"].assert_not_called()
    env["merge_enqueue"].assert_not_called()


def test_non_ara_agent_is_processed_but_not_merged(env):
    mesg = _message(results=[{"a": 1}])
    env["message_cls"].objects.get.return_value = mesg
    env["actor"].agent.name = "kp-test"
    tasks.ingest_ara_response.apply(args=(CHILD_PK, "D"))
    assert mesg.result_count == 1
    env["merge_enqueue"].assert_not_called()


def test_failure_marks_message_error_500(env):
    mesg = _message(results=[{"a": 1}])
    mesg.decompress_dict.side_effect = RuntimeError("corrupt body")
    env["message_cls"].objects.get.return_value = mesg

    result = tasks.ingest_ara_response.apply(args=(CHILD_PK, "D"))

    assert result.state == "SUCCESS"  # handled, not raised
    assert mesg.status == "E"
    assert mesg.code == 500
    mesg.save.assert_called()
    env["merge_enqueue"].assert_not_called()


def _bare_message():
    stub = MagicMock()
    stub.pk = "round-trip"
    stub.data = None
    return stub


def test_save_compressed_bytes_round_trips_without_parsing():
    """The view stores raw bytes; decompress_dict must read them back as the dict."""
    raw = b'{"message": {"results": [{"x": 1}]}, "logs": []}'
    mesg = _bare_message()
    Message.save_compressed_bytes(mesg, raw)
    assert mesg.data.startswith(b'\x28\xb5\x2f\xfd')  # zstd magic
    assert Message.decompress_dict(mesg) == {"message": {"results": [{"x": 1}]}, "logs": []}


def test_save_compressed_bytes_passes_through_already_compressed_data():
    raw = b'{"a": 1}'
    first = _bare_message()
    Message.save_compressed_bytes(first, raw)
    second = _bare_message()
    Message.save_compressed_bytes(second, first.data)
    assert second.data == first.data