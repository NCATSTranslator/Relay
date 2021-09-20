from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import sys, logging
from .models import Actor, Agent, Message, Channel
from .pubsub import send_messages

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Actor)
def actor_post_save(sender, instance, **kwargs):
    actor = instance
    logger.debug('+++ new actor updated/created by %s: %s...%s' % (
        sender, actor, actor.id))
    # now iterate through each message and pass it to the new actor
    # TODO add flag to turn on/off this behavior
    # TODO Currently failing because triggered before app is initialized to receive request
    #send_messages([actor], Message.objects.filter(code=200)
    #              .order_by('timestamp'))
            

@receiver(post_save, sender=Message)
def message_post_save(sender, instance, **kwargs):
    message = instance
    logger.debug('+++ post_save message: %s' % (message))
    # now broadcast the message to all actors only if it has code=200 and is a parent node
    if message.code == 200 and message.ref == None:
         if len(Message.objects.filter(ref__pk=message.pk)) == 0: # make sure we haven't already done this broadcast
            send_messages(Actor.objects.filter(channel = message.actor.channel), [message])
    # check if parent status should be updated to 'Done'
    if message.ref and message.status in ['D', 'S', 'E', 'U']:
        pmessage = message.ref
        if pmessage.status != 'D':
            children = Message.objects.filter(ref__pk=pmessage.pk)
            logger.debug('%s: %d children' % (pmessage.pk, len(children)))
            finished = True
            allError = True
            for child in children:
                if child.status not in ['D', 'S', 'E', 'U']:
                    finished = False
                if child.status not in ['S','E', 'U']:
                    allError = False
            if allError or finished:
                if allError:
                    pmessage.status = 'E'
                elif finished:
                    pmessage.status = 'D'
                pmessage.save()

@receiver(pre_save, sender=Message)
def message_pre_save(sender, instance, **kwargs):
    logger.debug('+++ pre_save message: %s' % instance)
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
