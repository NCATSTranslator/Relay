import factory
import logging
from faker import Faker
from tr_ars import models
from tests.helper.generate import get_ARA_response

logger = logging.getLogger('faker')
logger.setLevel(logging.INFO)
fake = Faker()


class AgentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Agent
        django_get_or_create = ("name",)
    name = 'agent_default'
    uri = 'ara-example/api/'

class ChannelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Channel
    name = 'test'
    description = fake.text()

class ActorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Actor

    agent = factory.SubFactory(AgentFactory)
    channel = 'test'
    path = 'runquery'
    inforesid = fake.word()
    active = 'True'

class MessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Message

    id = fake.uuid4()
    name = 'default_message'
    status = 'W'
    code = 200
    actor = factory.SubFactory(ActorFactory)
    data = get_ARA_response()
    retain=True

