"""
Unit tests for Message.save() and the compressed data it writes.

The ARA callback view and ingest_ara_response both load a child message, write new
data with save_compressed_bytes / save_compressed_dict and save it, and
merge_and_post_process then reads that row back. So save() must write the new data,
not the bytes the message was loaded with.

No DB: Model.save is patched to record the data that would be written.
"""
import json
import uuid
from unittest.mock import patch

import pytest
import zstandard as zstd
from django.db import models as django_models

from tr_ars.models import Actor, Agent, Message


QUERY = {"message": {"query_graph": {}}}
RESPONSE = {"message": {"results": [{"x": 1}], "knowledge_graph": {}}}


def _compress(d):
    return zstd.ZstdCompressor().compress(json.dumps(d).encode("utf-8"))


def _decompress(data):
    return json.loads(zstd.ZstdDecompressor().decompress(data))


def _with_actor(mesg):
    # save_compressed_dict logs the agent name
    mesg.actor = Actor(agent=Agent(name="ara-test"))
    return mesg


def _loaded(data):
    """A message built the way a queryset builds one, holding data already in the DB."""
    return _with_actor(Message.from_db("default", ["id", "data"], [uuid.uuid4(), _compress(data)]))


@pytest.fixture
def written():
    stored = []

    def record(self, *args, **kwargs):
        stored.append(self.data)

    with patch.object(django_models.Model, "save", record), \
         patch.object(Message, "should_notify", return_value=False):
        yield stored


def test_save_writes_bytes_stored_on_a_loaded_message(written):
    """The callback view: the stored query is replaced by the ARA's response body."""
    mesg = _loaded(QUERY)
    mesg.save_compressed_bytes(json.dumps(RESPONSE).encode("utf-8"))
    mesg.save()
    assert _decompress(written[-1]) == RESPONSE


def test_save_writes_dict_stored_on_a_loaded_message(written):
    """ingest_ara_response: the raw body is replaced by the pre_merge_process output."""
    processed = {"message": dict(RESPONSE["message"], processed=True)}
    mesg = _loaded(RESPONSE)
    mesg.save_compressed_dict(processed)
    mesg.save()
    assert _decompress(written[-1]) == processed


def test_save_leaves_loaded_data_unchanged_when_not_rewritten(written):
    mesg = _loaded(QUERY)
    loaded = mesg.data
    mesg.status = "R"
    mesg.save()
    assert written[-1] == loaded


def test_save_compresses_a_dict_passed_to_the_constructor(written):
    mesg = _with_actor(Message(data=RESPONSE))
    mesg.save()
    assert _decompress(written[-1]) == RESPONSE