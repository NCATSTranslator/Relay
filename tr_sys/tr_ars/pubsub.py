from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import sys, logging, threading
from .models import Actor, Agent, Message, Channel

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Actor)
def actor_post_save(sender, instance, **kwargs):
    actor = instance
    logger.debug('+++ new actor created: %s...%s' % (actor, actor.id))
    # now iterate through each message and pass it to the new actor
    SendMessage([actor], Message.objects.order_by('timestamp')).start()
            

@receiver(post_save, sender=Message)
def message_post_save(sender, instance, **kwargs):
    message = instance
    logger.debug('+++ new message created: %s' % (message))
    # now broadcast the message to all actors
    SendMessage(Actor.objects.all(), [message]).start()

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


class SendMessage(threading.Thread):
    def __init__(self, actors, mesgs, **kwargs):
        self.actors = actors
        self.messages = mesgs
        super(SendMessage, self).__init__(**kwargs)

    def run(self):
        for mesg in self.messages:
            for actor in self.actors:
                r = actor.consumes(mesg)
                if r != None:
                    logger.debug('%d: receive message from actor %s...\n%s'
                                 % (r.status_code, actor, r.text))
                    # now create a new message here
                    status = 'R'
                    if r.status_code != 200:
                        status = 'F'
                    mesg = Message(status=status, data=r.text,
                                   actor=actor, name=mesg.name,
                                   ref=mesg)
                    mesg.save()
