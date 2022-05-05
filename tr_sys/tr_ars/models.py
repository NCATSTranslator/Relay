from json import JSONDecodeError
from django.db import models
from django.utils import timezone
from django.core import serializers
import uuid, logging, json

logger = logging.getLogger(__name__)

# Create your models here.
class ARSModel(models.Model):
    class Meta:
        abstract = True

    def to_dict(self):
        return json.loads(serializers.serialize('json', [self]))[0]
    
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

    def __str__(self):
        return self.name

class Actor(ARSModel):
    channels = models.ManyToManyField(Channel, through='ActorIntermediateModel')
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
            self.pk, self.active, self.agent, self.channels, self.path)

    def url(self):
        return self.agent.uri+self.path

    def to_dict(self):
        jsonobj = ARSModel.to_dict(self)
        jsonobj['fields']['url'] = self.url()
        return jsonobj

class ActorIntermediateModel(ARSModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    actor = models.ForeignKey(Actor, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('channel', 'actor')

class Message(ARSModel):
    STATUS = (
        ('D', 'Done'),
        ('S', 'Stopped'),
        ('R', 'Running'),
        ('E', 'Error'),
        ('W', 'Waiting'),
        ('U', 'Unknown')
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.SlugField('Message name', null=False)
    code = models.PositiveSmallIntegerField('HTTP status code',
                                            null=False, default=200)
    status = models.CharField(max_length=2, choices=STATUS)
    actor = models.ForeignKey(Actor, null=False, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(null=False, default=timezone.now)
    data = models.JSONField('data payload', null=True)
    url = models.URLField('location of data', max_length=256, null=True)
    ref = models.ForeignKey('self', null=True, blank=True,
                            on_delete=models.CASCADE)
    
    def __str__(self):
        return "message[%s]{name:%s, status:%s}" % (self.id,
                                                    self.name, self.status)
    @classmethod
    def create(self, *args, **kwargs):
        # convert status long name to code for saving
        if 'status' in kwargs:
            for elem in Message.STATUS:
                if elem[1] == kwargs['status']:
                    kwargs['status'] = elem[0]
        return Message(*args, **kwargs)

    def to_dict(self):
        jsonobj = ARSModel.to_dict(self)
        # convert status code to long name for display
        if 'fields' in jsonobj:
            if 'status' in jsonobj['fields']:
                for elem in Message.STATUS:
                    if elem[0] == jsonobj['fields']['status']:
                        jsonobj['fields']['status'] = elem[1]
        return jsonobj


