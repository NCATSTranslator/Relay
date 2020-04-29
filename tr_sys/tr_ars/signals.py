from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import sys, logging
from .models import Actor, Agent, Message, Channel
from .pubsub import send_messages

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Actor)
def actor_post_save(sender, instance, **kwargs):
    actor = instance
    logger.debug('+++ new actor created: %s...%s' % (actor, actor.id))
    # now iterate through each message and pass it to the new actor
    send_messages([actor], Message.objects.filter(code=200)
                  .order_by('timestamp'))
            

@receiver(post_save, sender=Message)
def message_post_save(sender, instance, **kwargs):
    message = instance
    logger.debug('+++ new message created: %s' % (message))
    # now broadcast the message to all actors only if it has code=200
    if message.code == 200:
        send_messages(Actor.objects.all(), [message])

@receiver(pre_save, sender=Message)
def message_pre_save(sender, instance, **kwargs):
    # make sure no cycle
    message = instance
    if message.ref == message:
        logger.warning('Self-referencing message; removing reference!')
        message.ref = None

@receiver(post_save, sender=Channel)
def channel_post_save(sender, instance, **kwargs):
    channel = instance
    logger.debug('+++ new channel created: %s...%s' % (channel, channel.id))

@receiver(post_save, sender=Agent)
def agent_post_save(sender, instance, **kwargs):
    agent = instance
    logger.debug('+++ new agent created: %s...%s' % (agent, agent.id))
