import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)

class ARSAppConfig(AppConfig):
    name = 'tr_ars.default_ars_app'

#    def ready(self):
#        logger.debug('### %s ready...' % self.name)
