from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class NCATSConfig(AppConfig):
    name = 'tr_ara_ncats'

    def ready(self):
        logger.debug('### %s ready...' % self.name)
