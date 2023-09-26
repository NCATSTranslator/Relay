from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import sys, logging
from .models import Actor, Agent, Message, Channel
from .pubsub import send_messages
from .utils import get_safe
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
    msg = message.to_dict()
    data = get_safe(msg, "fields", "data")
    if data is not None:
        keyList = data.keys()
        if "allow_tools" in keyList and "deny_tools" in keyList:
            allow_tools=data['allow_tools']
            deny_tools =[]
            logger.error("Both an allow list and a deny list provided.  Taking only the allow list")
        elif "allow_tools" in keyList:
            allow_tools = data['allow_tools']
            deny_tools=[]
        elif "deny_tools" in keyList:
            deny_tools=data['deny_tools']
            allow_tools=[]
        else:
            allow_tools=[]
            deny_tools=[]

    if message.status == 'R':
        message.code = 202
    if message.status == 'D':
        message.code = 200
    logger.debug('+++ post_save message: %s with the code: %s' % (message, message.code))
    # now broadcast the message to all actors only if it has code=200 and is a parent node
    if message.code == 202 and message.ref == None:
        if len(Message.objects.filter(ref__pk=message.pk)) == 0: # make sure we haven't already done this broadcast
            matching_actors=[]
            for actor in Actor.objects.all():
                if (not allow_tools) and (not deny_tools):
                    for ch in actor.channel:
                        if ch in message.actor.channel:
                            print("match "+str(actor.inforesid))
                            matching_actors.append(actor)
                elif allow_tools and not deny_tools:
                    if str(actor.inforesid) in allow_tools:
                        matching_actors.append(actor)
                elif deny_tools and not allow_tools:
                    if str(actor.inforesid) not in deny_tools:
                        matching_actors.append(actor)
            #send_messages(Actor.objects.filter(message.actor.channel in channel), [message]) #this line will need to be changed to adapt to lists of channels
            send_messages(matching_actors, [message]) #this line will need to be changed to adapt to lists of channels

    # check if parent status should be updated to 'Done'
    if message.ref and message.status in ['D', 'S', 'E', 'U']:
        pmessage = message.ref
        if pmessage.status != 'D':
            children = Message.objects.filter(ref__pk=pmessage.pk)
            logger.debug('%s: %d children' % (pmessage.pk, len(children)))
            finished = True
            for child in children:
                if child.status not in ['D', 'S', 'E', 'U']:
                    finished = False

            if finished:
                pmessage.status = 'D'
                pmessage.code = 200
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
