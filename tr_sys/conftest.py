
import pytest
from pytest_factoryboy import register
from factories import UserFactory, AgentFactory, ActorFactory, MessageFactory, ChannelFactory


register(UserFactory)
register(AgentFactory)
register(ActorFactory)
register(ChannelFactory)
register(MessageFactory)



@pytest.fixture
def new_user(db, user_factory):
    user = user_factory.create()
    return user


@pytest.fixture
def test_agent(db, agent_factory):
    agent = agent_factory.create()
    return agent

@pytest.fixture
def test_channel(db, channel_factory):
    channel = channel_factory.create()
    return channel


@pytest.fixture
def test_actor(db, actor_factory):
    actor = actor_factory.create()
    return actor

@pytest.fixture
def test_message(db, message_factory):
    message = message_factory.create()
    return message


