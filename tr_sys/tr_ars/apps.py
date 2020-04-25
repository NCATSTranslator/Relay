from django.urls import reverse
from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging

logger = logging.getLogger(__name__)

DEFAULT_CHANNELS = [
    {'name':'general',
     'description': 'General channel for all queries'
     },
]

DEFAULT_AGENTS = [
    {'name': 'ars-default-agent',
     'description': 'Built-in ARS default agent',
     'uri': '', 
     'contact': 'ncatstranslator@nih.gov'
     }
]

DEFAULT_ACTORS = [
    {'channel': 'general',
     'agent': 'ars-default-agent',
     'path': ''
     }
]

def setup_schema(sender, **kwargs):
    logger.debug('setting up schema...')

    channels = {}
    Channel = sender.get_model('Channel')
    for c in DEFAULT_CHANNELS:
        name = c['name']
        channel, created = Channel.objects.get_or_create(
            name=name, defaults=c)
        channels[name] = channel

    agents = {}
    Agent = sender.get_model('Agent')
    for a in DEFAULT_AGENTS:
        name = a['name']
        agent, created = Agent.objects.get_or_create(
            name=name, defaults=a)
        agents[name] = agent

    Actor = sender.get_model('Actor')
    for a in DEFAULT_ACTORS:
        actor, created = Actor.objects.get_or_create(
            channel=channels[a['channel']], agent=agents[a['agent']],
            defaults={'path': a['path']})

class ARSConfig(AppConfig):
    name = 'tr_ars'

    def ready(self):
        # connect signals
        from . import pubsub
        logger.debug('### %s ready...' % self.name)
        post_migrate.connect(setup_schema, sender=self)
