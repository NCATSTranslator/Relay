from django.shortcuts import get_object_or_404
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import sys, logging
from .models import Actor, Agent, Message, Channel
from .pubsub import send_messages
from .utils import get_safe, createMessage
from django.utils import timezone
logger = logging.getLogger(__name__)
from .api import query_event_unsubscribe,get_ars_actor

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
    # --- Prevent recursion / internal saves ---
    if getattr(instance, "_skip_post_save", False):
        return
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
                    logger.info('+++ Parent message %s not Done because of child: %s in state %s' % (str(pmessage.id),str(child.id),str(child.status)))

                if child.status == 'D' and child.actor.agent.name.startswith('ar') and (child.result_count is not None and child.result_count > 0):
                    if child.actor.agent.name == 'ars-ars-agent':
                        merge_count += 1
                    else:
                        orig_count += 1
                if child.status == 'E' and child.actor.agent.name == 'ars-ars-agent':
                    if child.code == 444:
                        merge_count += 1
                    else:
                        logger.info('+++ a merged message Errored out, removing its count from orig_count pk: %s & parent_pk: %s'% (str(child.pk),str(pmessage.id)))
                        orig_count -= 1
            logger.info('+++ so far parent_pk: %s merge_count: %s & orig_count: %s '% (str(pmessage),merge_count,orig_count))
            if finished and merge_count == orig_count:
                logger.info('+++ Parent message Done for: %s \n Attempting save' % (str(pmessage.id)))
                logger.info('Children count is: %s.' % (str(len(children))))
                logger.info('Merge count is:  %s' % (str(merge_count)))
                logger.info('Original count is: %s.' % (str(orig_count)))
                #create an empty merged message
                if merge_count==0 and orig_count==0:
                    empty_merged_mesg= createMessage(get_ars_actor(),str(pmessage.pk))
                    empty_data = pmessage.decompress_dict()
                    empty_data['message']['results']=[]
                    empty_data['message']['auxiliary_graphs']={}
                    empty_data['message']['knowledge_graph']={}
                    empty_data['message']['knowledge_graph']['nodes']= {}
                    empty_data['message']['knowledge_graph']['edges']={}

                    empty_merged_mesg._skip_post_save = True
                    empty_merged_mesg.save_compressed_dict(empty_data)

                    empty_merged_mesg.code=200
                    empty_merged_mesg.status='D'
                    empty_merged_mesg._skip_post_save = True
                    empty_merged_mesg.save()
                    pmessage.merged_version=empty_merged_mesg
                    pmessage.merged_versions_list=[(str(empty_merged_mesg.id), "ars")]
                    pmessage.status = 'D'
                    pmessage.code = 200
                    pmessage.updated_at = timezone.now()
                    pmessage._skip_post_save = True
                    pmessage.save(update_fields=['status','code','updated_at', 'merged_version', 'merged_versions_list'])
                else:
                    pmessage.status = 'D'
                    pmessage.code = 200
                    pmessage.updated_at = timezone.now()
                    pmessage.save(update_fields=['status','code','updated_at'])
                    query_event_unsubscribe(None, pmessage.pk)
            elif pmessage.status == 'E':
                query_event_unsubscribe(None, pmessage.pk)
            else:
                logger.info('+++ Parent message not Done for: %s \n' % (str(pmessage.id)))
                logger.info ("Finished, merge_count, and orig_count: %s, %s, %s" % (str(finished),str(merge_count),str(orig_count)))
        else:
            logger.info('Checking doneness for parent already in done state: %s' % (str(pmessage.id)))


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
