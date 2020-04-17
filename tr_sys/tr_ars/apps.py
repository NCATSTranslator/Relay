from django.apps import AppConfig

class ARSConfig(AppConfig):
    name = 'tr_ars'

    def ready(self):
        from .pubsub import actor_handler
        print ('ARS config...')
