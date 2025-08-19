import pytest,requests
from unittest.mock import patch, MagicMock, Mock
from django.db.utils import OperationalError
from django.urls import reverse
from tr_ars.utils import canonize
from tr_ars.models import Message



#here client is Django's test client
def test_home_url(client):
     url = reverse("ars-app-home")
     response = client.get(url)
     assert response.status_code == 200

def test_agent_str(test_agent):
     assert test_agent.__str__() == 'agent{name:agent_default, uri:ara-example/api/}'

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
     assert actor.url() == actor.agent.uri+actor.path


@pytest.mark.django_db
def test_message_str(test_message):
     msg = test_message
     assert msg.__str__() == "message[%s]{name:default_message, status:W}" % (msg.id)

@pytest.mark.django_db
def test_message_save(test_message):
     assert Message.objects.filter(id=test_message.id).exists()

@pytest.mark.django_db
def test_message_compression_decompression(test_message):
     decompressed_data = test_message.decompress_dict()
     assert isinstance(decompressed_data, dict)
     assert isinstance(test_message.data, (bytes, bytearray))
     assert test_message.data.startswith(b'\x28\xb5\x2f\xfd')
     assert 'results' in decompressed_data.get('message').keys()

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


@pytest.mark.django_db
def test_health_check_all_ok(client):
     with patch("tr_ars.tasks.health_ping.apply") as mock_celery:

          # Simulate celery returning "pong"
          mock_result = MagicMock()
          mock_result.get.return_value = "pong"
          mock_celery.return_value = mock_result

          response = client.get(reverse("ars-health"))
          print(response.content)
          print(response.status_code)
          print(response.content.decode())
          data = response.json()

          assert response.status_code == 200
          assert data["status"] == "ok"
          assert data["database"] == "available"
          assert data["celery"] == "available"


@pytest.mark.django_db
def test_health_check_db_error(client):
     # we want to unit test a graceful DB failure to ensure health endpoint respond correctly when DB is unavailbale
     with patch("tr_ars.api.connections") as mock_connections: #replaces Django's db connection object with a mock

          mock_connections.__getitem__.return_value.cursor.side_effect = OperationalError() #=> .cursor() here mock DB connection & operationalError is simulating a DB failure
          #any attempt in calling .cursor() on this mock DB will raise error
          response = client.get(reverse("ars-health"))
          data = response.json()

          assert response.status_code == 500
          assert data["status"] == "error"
          assert data["database"] == "unavailable"

# no real external call, just testing the mock tracer and HTTP request post
def test_request_call_success(mock_tracer, mock_span):
     with patch("tr_ars.utils.trace.get_tracer", return_value=mock_tracer):
          with patch("tr_ars.utils.requests.post") as mock_post: #mocking HTTP call
               mock_response = Mock() #this generic mock object simulate the HTTP response object returned by request.post
               mock_response.json.return_value = {"normalized": True} #configure the .json() method of mocked_response return the normalized:true  to simulate successfull json response
               mock_post.return_value = mock_response #tells mocked_post to return the mocked response whenever called

               curies = ['MESH:D014867', 'NCIT:C34373'] #test input
               result = canonize(curies)

               assert result == {"normalized": True}
               mock_post.assert_called_once() #verifies that req.post was called only once
               mock_span.set_attribute.assert_not_called() #this ensures that no errors was recorded on the span


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