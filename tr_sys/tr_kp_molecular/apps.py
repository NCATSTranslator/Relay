from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class MolecularConfig(AppConfig):
    name = 'tr_kp_molecular'

    def ready(self):
        logger.debug('### %s ready...' % self.name)
