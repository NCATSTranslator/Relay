import gzip
from django.shortcuts import get_object_or_404
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import sys, logging
from .models import Actor, Agent, Message, Channel, QueryGraphPlus
from .pubsub import send_messages
from .utils import get_safe
logger = logging.getLogger(__name__)
from .api import query_event_unsubscribe

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
                for ch in actor.channel:
                    if ch in message.actor.channel:
                        print("match "+str(actor.inforesid))
                        matching_actors.append(actor)
            #send_messages(Actor.objects.filter(message.actor.channel in channel), [message]) #this line will need to be changed to adapt to lists of channels
            send_messages(matching_actors, [message]) #this line will need to be changed to adapt to lists of channels

    # check if parent status should be updated to 'Done'
    if message.ref is not None and message.status in ['D', 'S', 'E', 'U']:
        logger.info('+++ checking parent Doneness: %s for message/parent: %s %s' % (message.ref.status, str(message.id), str(message.ref.id)))
        stat_plus={}
        pmessage = message.ref
        if pmessage.status != 'D':
            logger.info('+++ Parent message not Done for: %s' % (str(pmessage.id)))
            children = Message.objects.filter(ref__pk=pmessage.pk)
            logger.info('%s: %d children' % (pmessage.pk, len(children)))
            finished = True
            merge_count=0
            orig_count=0
            for child in children:
                if child.status not in ['D', 'S', 'E', 'U']:
                    finished = False
                    #logger.info('+++ Parent message %s not Done because of child: %s in state %s' % (str(pmessage.id),str(child.id),str(child.status)))

                if child.status == 'D' and child.actor.agent.name.startswith('ar') and (child.result_count is not None and child.result_count > 0):
                    if child.actor.agent.name == 'ars-ars-agent':
                        merge_count += 1
                    else:
                        orig_count += 1
                if child.status == 'E' and child.actor.agent.name == 'ars-ars-agent':
                    logger.info('+++ a merged message Errored out, removing its count from orig_count pk: %s & psrent_pk: %s'% (str(child.pk),str(pmessage.id)))
                    orig_count -= 1
            logger.info('+++ so far parent_pk: %s merge_count: %s & orig_count: %s '% (str(pmessage),merge_count,orig_count))
            if finished and merge_count == orig_count:
                logger.info('+++ Parent message Done for: %s \n Attempting save' % (str(pmessage.id)))
                pmessage.status = 'D'
                pmessage.code = 200
                pmessage.save(update_fields=['status','code'])
                query_event_unsubscribe(None, pmessage.pk)
                #save the record to query graph plus table
                for child in children:
                    stat_plus[child.actor.inforesid]=(child.code, child.result_count, child.result_stat)
                data=pmessage.decompress_dict()
                querygraph = QueryGraphPlus.create(query_graph=data['message']['query_graph'], timestamp=pmessage.updated_at, stats=stat_plus)
                querygraph.save()

            elif pmessage.status == 'E':
                query_event_unsubscribe(None, pmessage.pk)


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
