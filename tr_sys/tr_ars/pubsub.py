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
    SendMessage([actor], Message.objects.filter(code=200)
                .order_by('timestamp')).start()
            

@receiver(post_save, sender=Message)
def message_post_save(sender, instance, **kwargs):
    message = instance
    logger.debug('+++ new message created: %s' % (message))
    # now broadcast the message to all actors only if it has code=200
    if message.code == 200:
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
        messages = []
        for mesg in self.messages:
            for actor in self.actors:
                r = actor.consumes(mesg)
                if r != None:
                    logger.debug('%d: receive message from actor %s...\n%s.\n'
                                 % (r.status_code, actor, r.text))
                    if r.status_code != 204:
                        # now create a new message here
                        status = 'U'
                        if 'tr_ars.message.status' in r.headers:
                            status = r.headers['tr_ars.message.status']
                        mesg = Message(code=r.status_code, status=status,
                                       data=r.text, actor=actor,
                                       name=mesg.name, ref=mesg)
                        messages.append(mesg)
        for mesg in messages:
            mesg.save()
