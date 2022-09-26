import pytest
from django.urls import reverse
import time
import os
import requests

def test_home_url(client):
     url = reverse("ars-app-home")
     response = client.get(url)
     assert response.status_code == 200

#------test for string model specific return-------
def test_agent_str(test_agent):
    assert test_agent.__str__() == 'agent{name:agent_default, uri:ara-example/api/}'

#------ test for agent endpoint ----------
@pytest.mark.django_db
def test_agents_response(client):
     url = reverse("ars-agents")
     response = client.get(url)
     assert response.status_code == 200

#------ test for agent endpoint ----------
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

# @pytest.mark.django_db
def test_actor_str(test_actor):
     actor = test_actor
     assert actor.__str__() == "actor{pk:%s, active:True, %s, channel:test, path:runquery}" % (actor.pk, actor.agent)

#-----------------url validation for actors------------------------
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

#------------------------ Testing for Selenium Webdriver -------------
# def take_screenshot(driver, name):
#      time.sleep(1)
#      os.makedirs(os.path.join("screenshot", os.path.dirname(name)), exist_ok=True)
#      driver.save_screenshot(os.path.join("screenshot", name))
#
# @pytest.mark.usefixtures("driver_init")
# class Test_url_opening_and_screenshots:
#      def test_screenshot_admin(self, live_server):
#         self.driver.get(("%s%s" % (live_server.url, "/admin/")))
#         take_screenshot(self.driver, "admin/" + "admin" + self.browser + ".png")
#         assert "Log in | Django site admin" in self.driver.title
