
import pytest
from pytest_factoryboy import register
#from factories import AgentFactory, ActorFactory, MessageFactory, ChannelFactory
from factories import ChannelFactory
from selenium import webdriver

#
# register(AgentFactory)
# register(ActorFactory)
register(ChannelFactory)
# register(MessageFactory)
#
#
#
# @pytest.fixture
# def new_user(db, user_factory):
#     user = user_factory.create()
#     return user
#
#
# @pytest.fixture
# def test_agent(db, agent_factory):
#     agent = agent_factory.create()
#     return agent

@pytest.fixture
def test_channel(db, channel_factory):
    channel = channel_factory.create()
    return channel

#
# @pytest.fixture
# def test_actor(db, actor_factory):
#     actor = actor_factory.create()
#     return actor
#
# @pytest.fixture
# def test_message(db, message_factory):
#     message = message_factory.create()
#     return message

# @pytest.fixture(params=["firefox"], scope="class")
# def driver_init(request):
#     if request.param == "chrome1920":
#         options = webdriver.ChromeOptions()
#         options.add_argument("--headless")
#         options.add_argument("--window-size=1920,1080")
#         web_driver = webdriver.Chrome(options=options)
#         request.cls.browser = "Chrome1920x1080"
#     if request.param == "chrome411":
#         options = webdriver.ChromeOptions()
#         options.add_argument("--headless")
#         options.add_argument("--window-size=411,823")
#         web_driver = webdriver.Chrome(options=options)
#         request.cls.browser = "Chrome411x823"
#     if request.param == "firefox":
#         options = webdriver.FirefoxOptions()
#         options.add_argument("--headless")
#         web_driver = webdriver.Firefox(options=options)
#         request.cls.browser = "Firefox"
#     request.cls.driver = web_driver
#     yield
#     web_driver.close()
