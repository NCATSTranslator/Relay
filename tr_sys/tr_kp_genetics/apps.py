from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class GeneticsConfig(AppConfig):
    name = 'tr_kp_genetics'

    def ready(self):
        logger.debug('### %s ready...' % self.name)
