from json import JSONDecodeError

import requests as requests
from django.db import models
from django.utils import timezone
from django.core import serializers
import uuid, logging, json
import gzip
logger = logging.getLogger(__name__)
# Create your models here.


class ARSModel(models.Model):
    class Meta:
        abstract = True
    def to_dict(self):
        return json.loads(serializers.serialize('json', [self]))[0]

class Client(ARSModel):
    client_id= models.TextField('name of client',null =False)
    client_secret=models.TextField('hash of client secret', null = False)
    callback_url=models.URLField('default URL for the client',null=False,max_length=256)
    date_created=models.DateTimeField(auto_now_add=True) #Automatically set at creation
    date_secret_updated=models.DateTimeField(auto_now=True)
    active=models.BooleanField(default=False)
    subscriptions = models.JSONField('List of pks to which a client is curently subscribed',null=True,blank=True)

class Agent(ARSModel):
    name = models.SlugField('agent unique name',
                            null=False, unique=True, max_length=128)
    description = models.TextField('description of agent', null=True)
    uri = models.URLField('base url of agent', null=False, max_length=256)
    contact = models.EmailField(null=True)
    registered = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)
        
    def __str__(self):
        return 'agent{name:%s, uri:%s}' % (self.name, self.uri)

class Channel(ARSModel):
    name = models.SlugField('channel name', unique=True,
                            null=False, max_length=128)
    description = models.TextField('description of channel', null=True)
    #channels = models.ManyToManyField('self')

    def __str__(self):
        return self.name

class Actor(ARSModel):
    #channel = models.SeparatedValuesField(Channel)
    channel=models.JSONField(null=True)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    path = models.CharField('relative path of actor', max_length=64)
    inforesid = models.CharField('inforesid', blank=True, max_length=500)
    active = models.BooleanField('actor is active', default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['agent', 'path'],
                                    name='unique_actor')
        ]
    def __str__(self):
        return "actor{pk:%s, active:%s, %s, channel:%s, path:%s}" % (
            self.pk, self.active, self.agent, self.channel, self.path)

    def url(self):
            return self.agent.uri+self.path

    def to_dict(self):
        jsonobj = ARSModel.to_dict(self)
        jsonobj['fields']['url'] = self.url()
        return jsonobj


class Message(ARSModel):
    STATUS = (
        ('D', 'Done'),
        ('S', 'Stopped'),
        ('R', 'Running'),
        ('E', 'Error'),
        ('W', 'Waiting'),
        ('U', 'Unknown')
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, db_index=True)
    name = models.SlugField('Message name', null=False)
    code = models.PositiveSmallIntegerField('HTTP status code',
                                            null=False, default=200)
    status = models.CharField(max_length=2, choices=STATUS, db_index=True)
    actor = models.ForeignKey(Actor, null=False, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True,db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    #data = models.JSONField('data payload', null=True)
    data = models.BinaryField('data payload', null=True)
    url = models.URLField('location of data', max_length=256, null=True)
    ref = models.ForeignKey('self', null=True, blank=True,
                            on_delete=models.CASCADE)
    result_count = models.IntegerField(null=True, default=None)
    result_stat = models.JSONField(null=True)
    retain = models.BooleanField('flag to retain data', default=False)
    merge_semaphore=models.BooleanField('flag to indicate that merging is currently in progress',default=False)
    merged_version = models.ForeignKey('self', related_name="version_merged",null=True, blank=True,
                                     on_delete=models.CASCADE)
    merged_versions_list= models.JSONField('Ordered list of merged_version PKs', null=True)
    params = models.JSONField(null=True)
    clients = models.ManyToManyField(Client, related_name="messages")


    def __str__(self):
        return "message[%s]{name:%s, status:%s}" % (self.id,
                                                    self.name, self.status)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # # Decompress the compressed data when initializing the model instance
        if self.data and self.data is not None:
            self.original_data = self.data
        else:
            self.original_data = {}

    def save(self, *args, **kwargs):
        # Compress the data before saving
        logger.info("Entering save")
        if self.original_data:
            logger.info('Compressing the data at save call')
            self.save_compressed_dict(self.original_data)
            self.original_data = {}  # Clear original data to avoid redundancy

        super().save(*args, **kwargs)
        if self.should_notify():
            self.notify_subscribers()

    def save_compressed_dict(self, data):
        try:
            if isinstance(data, (bytes, bytearray)) and data is not None and data.startswith(b'\x1f\x8b'):
                logger.info('data already compressed, no action needed')
                self.data = data
            else:
                logger.info('compressing the data with pk: %s' % str(self.pk))
                # Convert dictionary to JSON string
                json_data = json.dumps(data, default=str)

                # Compress JSON string using gzip
                compressed_data = gzip.compress(json_data.encode('utf-8'))

                # Save compressed data to the model field
                self.data = compressed_data
        except Exception as e:
            print("Error compressing data:", e)

    def decompress_dict(self):
        try:
            #check to see if you are dealing with dictionary or compressed data?
            if isinstance(self.data, dict):
                original_data = self.data
            elif isinstance(self.data, (bytes, bytearray)) and self.data is not None:
                #logger.info('decompressing the data if binary %s'% str(self.pk))
                if self.data.startswith(b'\x1f\x8b'):
                    # Decompress the compressed data
                    decompressed_data = gzip.decompress(self.data)

                    # Convert decompressed bytes to JSON string
                    json_data = decompressed_data.decode('utf-8')

                    # Convert JSON string back to dictionary
                    original_data = json.loads(json_data)
                else:
                    # Convert plain text bytes to JSON string
                    json_data = self.data.decode('utf-8')
                    # Convert JSON string back to dictionary
                    original_data = json.loads(json_data)

            return original_data
        except Exception as e:
            print("Error decompressing data:", e)
            return {}
    @classmethod
    def create(self, *args, **kwargs):
        # convert status long name to code for saving
        logger.info('creating Message model instance')
        if 'status' in kwargs:
            for elem in Message.STATUS:
                if elem[1] == kwargs['status']:
                    kwargs['status'] = elem[0]
        return Message(*args, **kwargs)

    def to_dict(self):
        logger.info('running to_dict call on message object with pk %s'% str(self.pk))
        jsonobj = ARSModel.to_dict(self)
        # convert status code to long name for display
        if 'fields' in jsonobj:
            if 'status' in jsonobj['fields']:
                for elem in Message.STATUS:
                    if elem[0] == jsonobj['fields']['status']:
                        jsonobj['fields']['status'] = elem[1]
            if 'data' in jsonobj['fields'] and jsonobj['fields']['data'] is not None:
                jsonobj['fields']['data'] = self.decompress_dict()
        return jsonobj

    def notify_subscribers(self, additional_notification_fields=None):
        from .tasks import notify_subscribers_task
        if self.status == 'D':
            additional_notification_fields = {
                "event_type":"admin",
                "complete" : True
            }
        if self.status == 'E':
            additional_notification_fields = {
                "event_type":"ars_error",
                "message":'We had a huge problem',
                "complete" : True
            }
        #offload to a celery task
        notify_subscribers_task.apply_async((self.pk, self.code, additional_notification_fields))

    def should_notify(self):
        return self.status in ('D', 'E')


