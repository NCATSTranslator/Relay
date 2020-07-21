from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class UnsecretConfig(AppConfig):
    name = 'tr_ara_unsecret'

    def ready(self):
        logger.debug('### %s ready...' % self.name)
