from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class ARAXConfig(AppConfig):
    name = 'tr_ara_arax'

    def ready(self):
        logger.debug('### %s ready...' % self.name)
