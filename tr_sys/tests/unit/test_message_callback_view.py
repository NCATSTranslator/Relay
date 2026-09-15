"""
Unit tests for the ARA callback view (POST /ars/api/messages/<pk>).

The view must never parse the body: it applies the duplicate guards
from the row alone, stores the raw bytes compressed, enqueues
ingest_ara_response on commit, and returns a small acknowledgement rather than
serializing the whole message back out.
"""
import json
from unittest.mock import patch, MagicMock

import pytest
from django.test import RequestFactory

from tr_ars import api


KEY = "2c1a9a5e-3a4e-4c0e-9d1c-1b1a0c3b2f11"
BODY = b'{"message": {"results": [{"a": 1}], "knowledge_graph": {}}}'


def _mesg(status="R", result_count=None, code=202):
    mesg = MagicMock()
    mesg.pk = KEY
    mesg.status = status
    mesg.result_count = result_count
    mesg.code = code
    return mesg


@pytest.fixture
def env():
    # Replace the module's `json` reference (not the global json module, which the
    # tests themselves use) so any parse of the body inside the view fails loudly.
    json_stub = MagicMock()
    json_stub.loads.side_effect = AssertionError("view must not parse the body")
    with patch.object(api, "Message") as message_cls, \
         patch.object(api, "transaction") as txn, \
         patch.object(api.tasks.ingest_ara_response, "apply_async") as enqueue, \
         patch.object(api, "json", json_stub):
        message_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
        txn.on_commit.side_effect = lambda fn: fn()
        yield {"message_cls": message_cls, "enqueue": enqueue}


def _post(body=BODY, headers=None):
    req = RequestFactory().post(f"/ars/api/messages/{KEY}", data=body,
                                content_type="application/json")
    if headers:
        req.headers = headers
    return req


def test_callback_is_stored_raw_and_ingest_is_enqueued(env):
    mesg = _mesg()
    env["message_cls"].objects.get.return_value = mesg

    resp = api.message(_post(), KEY)

    assert resp.status_code == 201
    mesg.save_compressed_bytes.assert_called_once_with(BODY)
    mesg.save.assert_called_once()
    env["enqueue"].assert_called_once_with((KEY, "D"))
    # a small ack, not the whole message serialized back out
    payload = json.loads(resp.content)
    assert payload == {"pk": KEY, "status": "Accepted", "code": 202}
    mesg.to_dict.assert_not_called()


def test_status_header_is_forwarded_to_the_task(env):
    env["message_cls"].objects.get.return_value = _mesg()
    resp = api.message(_post(headers={"tr_ars.message.status": "S"}), KEY)
    assert resp.status_code == 201
    env["enqueue"].assert_called_once_with((KEY, "S"))


@pytest.mark.parametrize("mesg,expected_status", [
    (_mesg(status="D"), 200),
    (_mesg(status="R", result_count=5), 409),
    (_mesg(status="E", code=500), 400),
])
def test_duplicate_guards_reject_without_storing_or_enqueueing(env, mesg, expected_status):
    env["message_cls"].objects.get.return_value = mesg
    resp = api.message(_post(), KEY)
    assert resp.status_code == expected_status
    mesg.save_compressed_bytes.assert_not_called()
    mesg.save.assert_not_called()
    env["enqueue"].assert_not_called()


def test_unknown_pk_is_404(env):
    env["message_cls"].objects.get.side_effect = env["message_cls"].DoesNotExist
    resp = api.message(_post(), KEY)
    assert resp.status_code == 404
    env["enqueue"].assert_not_called()


def test_large_body_is_never_parsed_in_the_request(env):
    """The whole point of the change: the body size must not matter to the view."""
    env["message_cls"].objects.get.return_value = _mesg()
    big = b'{"message": {"results": [' + b'{"a": 1},' * 200000 + b'{"a": 1}]}}'
    resp = api.message(_post(body=big), KEY)
    assert resp.status_code == 201  # json.loads is patched to raise if called