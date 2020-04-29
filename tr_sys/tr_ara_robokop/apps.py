from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class RobokopConfig(AppConfig):
    name = 'tr_ara_robokop'

    def ready(self):
        logger.debug('### %s ready...' % self.name)
