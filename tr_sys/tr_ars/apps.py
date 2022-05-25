from django.urls import reverse
from django.apps import AppConfig
from django.db.models.signals import post_migrate
import logging, os, signal, sys

logger = logging.getLogger(__name__)

DEFAULT_CHANNELS = [
    {'name':'general',
     'description': 'General channel for all queries'
     },
    {'name':'workflow',
     'description': 'Channel for queries containing workflow and operations parameters'
     }
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
     'path': '',
     'team': 'ars_general'
     },
    {'channel': 'workflow',
     'agent': 'ars-default-agent',
     'path': '',
     'team': 'ars_workflow'
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
            defaults={'path': a['path'],
                    'inforesid': a['inforesid'],
                    'team': a['team']})

def my_signal_handler(*args):
    if os.environ.get('RUN_MAIN') == 'true':  
        logger.debug('STOPPED')
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver':
        from . import pubsub    
        pubsub.queue.put((None, None))
    sys.exit(0)
        
class ARSConfig(AppConfig):
    name = 'tr_ars'

    def ready(self):
        # connect signals
        from . import signals
        from django.conf import settings
        logger.debug('### %s ready...CELERY=%s' % (
            self.name, settings.USE_CELERY))
        #post_migrate.connect(setup_schema, sender=self)
        signal.signal(signal.SIGINT, my_signal_handler)
