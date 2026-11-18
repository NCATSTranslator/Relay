import uuid
from unittest.mock import patch

import pytest

from tr_ars.models import Actor, Agent, Message


def make_actor(agent_name):
    agent, _ = Agent.objects.get_or_create(name=agent_name, defaults={"uri": "http://example/"})
    actor, _ = Actor.objects.get_or_create(agent=agent, path="runquery",
                                           defaults={"channel": ["test"], "inforesid": agent_name})
    return actor


def make_message(actor, status, ref=None, result_count=None, code=None):
    if code is None:
        code = 202 if status == "R" else 200
    return Message.objects.create(id=uuid.uuid4(), name="m", status=status, actor=actor,
                                  code=code, ref=ref, result_count=result_count)


@pytest.fixture
def no_side_effects(db):
    """Keep the post_save handler from broadcasting to actors or notifying subscribers."""
    with patch("tr_ars.signals.send_messages"), \
         patch("tr_ars.signals.query_event_unsubscribe"), \
         patch.object(Message, "notify_subscribers"):
        yield


@pytest.fixture
def query(no_side_effects):
    """A running query: one ARA has answered and been merged, the other is still running."""
    ars = make_actor("ars-ars-agent")
    parent = make_message(ars, "R")
    make_message(make_actor("ara-one"), "D", ref=parent, result_count=5)
    running_child = make_message(make_actor("ara-two"), "R", ref=parent)
    merged = make_message(ars, "D", ref=parent, result_count=5)
    merged.save_compressed_dict({"message": {"results": [{}], "auxiliary_graphs": {}}})
    merged.save()
    parent.merged_version = merged
    parent.save(update_fields=["merged_version"])
    return {"parent": parent, "running_child": running_child, "ars": ars, "merged": merged}


def test_query_is_done_when_every_ara_has_finished_and_been_merged(query):
    child = query["running_child"]
    child.status = "D"
    child.result_count = 3
    child.save()
    assert Message.objects.get(pk=query["parent"].pk).status == "R"  # answered, not yet merged

    make_message(query["ars"], "D", ref=query["parent"], result_count=7)

    assert Message.objects.get(pk=query["parent"].pk).status == "D"


def test_query_is_done_when_the_remaining_ara_errors(query):
    """An errored ARA has nothing to merge, so its own save must complete the query."""
    child = query["running_child"]
    child.status = "E"
    child.code = 500
    child.save()

    assert Message.objects.get(pk=query["parent"].pk).status == "D"


@pytest.mark.parametrize("code", [444, 500])
def test_query_is_done_when_the_last_merge_errors(query, code):
    """A failed merge does not hang the query, whichever error code it carries."""
    child = query["running_child"]
    child.status = "D"
    child.result_count = 3
    child.save()
    assert Message.objects.get(pk=query["parent"].pk).status == "R"

    make_message(query["ars"], "E", ref=query["parent"], code=code)

    assert Message.objects.get(pk=query["parent"].pk).status == "D"


def test_query_with_no_results_is_done_with_an_empty_merged_message(no_side_effects):
    ars = make_actor("ars-ars-agent")
    parent = make_message(ars, "R")
    parent.save_compressed_dict({"message": {"query_graph": {"nodes": {}, "edges": {}}}})
    parent.save()
    first = make_message(make_actor("ara-one"), "R", ref=parent)
    second = make_message(make_actor("ara-two"), "R", ref=parent)

    first.status = "D"
    first.result_count = 0
    first.save()
    assert Message.objects.get(pk=parent.pk).status == "R"  # the other ARA is still running

    with patch("tr_ars.signals.get_ars_actor", return_value=ars):
        second.status = "D"  # done, result_count never set
        second.save()

    parent = Message.objects.get(pk=parent.pk)
    assert parent.status == "D"
    assert parent.code == 200
    merged = parent.merged_version
    assert merged.status == "D"
    assert parent.merged_versions_list == [[str(merged.id), "ars"]]
    message = merged.decompress_dict()["message"]
    assert message["results"] == []
    assert message["knowledge_graph"] == {"nodes": {}, "edges": {}}
    assert message["query_graph"] == {"nodes": {}, "edges": {}}