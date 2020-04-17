from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Actor, Agent, State

@receiver(post_save, sender=Actor)
def actor_handler(sender, instance, **kwargs):
    actor = instance
    print('new actor %s created!' % actor.id)

@receiver(post_save, sender=State)
def state_handler(sender, instance, **kwargs):
    state = instance
    print('new state %s created!' % state.id)
