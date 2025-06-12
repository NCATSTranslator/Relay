import pytest
from unittest.mock import patch
from django.urls import reverse

def test_home_url(client):
     url = reverse("ars-app-home")
     response = client.get(url)
     assert response.status_code == 200

def test_agent_str(test_agent):
    assert test_agent.__str__() == 'agent{name:agent_default, uri:ara-explanatory/api/}'

@pytest.mark.django_db
def test_agents_response(client):
     url = reverse("ars-agents")
     response = client.get(url)
     assert response.status_code == 200

@pytest.mark.django_db
@pytest.mark.usefixtures("agent_factory")
def test_agent_response(client, test_agent):
     agent = test_agent
     url = reverse("ars-agent", args=[agent.name])
     response = client.get(url)
     assert response.status_code == 200

@pytest.mark.django_db
def test_channel_str(test_channel):
    assert  test_channel.__str__() == 'test'

def test_actor_str(test_actor):
     actor = test_actor
     assert actor.__str__() == "actor{pk:%s, active:True, %s, channel:test, path:runquery}" % (actor.pk, actor.agent)

@pytest.mark.django_db
def test_actor_url(test_actor):
     actor = test_actor
     return actor.url() == actor.agent.uri+actor.path

@pytest.mark.django_db
def test_message_str(test_message):
     msg = test_message
     assert msg.__str__() == "message[%s]{name:default_message, status:W}" % (msg.id)

@pytest.mark.django_db
def test_messages_response(client, test_message):
     msg = test_message
     url = reverse('ars-message', args=[msg.id])
     response = client.get(url)
     assert response.status_code == 200

@pytest.mark.django_db
def test_notify_subscribers_success(test_message):
     with patch("tr_ars.tasks.notify_subscribers_task.apply_async") as mock_apply_async:
          test_message.status = 'D'
          test_message.save()
          test_message.notify_subscribers()

          mock_apply_async.assert_called_once() #asserts that the apply_async method was called excatly one time
          args, kwargs = mock_apply_async.call_args #retrieves the positional args and keyword arguments that were passed on the mocked apply async call
          assert args[0][0] == test_message.pk
          assert args[0][1] == test_message.code
          assert args[0][2]["complete"] is True


# @pytest.mark.django_db
# def test_send_mesg_task_triggered(test_actor, test_message, mock_send_message):
#      actor_dict= test_actor.to_dict()
#      message_dict=test_message.to_dict()
#      #Simulate task call
#      from tr_ars.tasks import send_message
#      send_message(actor_dict, message_dict)
#
#      # Verify the Celery task was called with correct arguments
#      mock_send_message.assert_called_once_with(actor_dict, message_dict)