from django.db import models
from django.utils import timezone

# Create your models here.
class Agent(models.Model):
    name = models.SlugField('agent unique name', null=False)
    description = models.TextField('description of agent')
    uri = models.URLField('base url of agent', null=False, max_length=256)
    contact = models.EmailField()
    registered = models.DateTimeField(default=timezone.now)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Channel(models.Model):
    name = models.SlugField('channel name', null=False, primary_key=True)
    description = models.TextField('description of channel')

    def __str__(self):
        return self.name
    
class Actor(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    path = models.CharField('relative path of agent', max_length=64)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['channel', 'agent', 'path'],
                                    name='unique_actor')
        ]

    def __str__(self):
        return "actor[%s]{agent:%s, channel:%s, path:%s}" % (
            self.id, self.agent, self.channel, self.path)
    
class State(models.Model):
    STATUES = (
        ('D', 'Done'),
        ('S', 'Stopped'),
        ('R', 'Running'),
        ('E', 'Error'),
        ('W', 'Waiting')
    )
    name = models.SlugField('state name', null=False)
    status = models.CharField(max_length=2, choices=STATUES)
    actor = models.ForeignKey(Actor, null=False, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(null=False, default=timezone.now)
    data = models.BinaryField('data payload', null=True)
    url = models.URLField('location of data', max_length=256, null=True)
    ref = models.ForeignKey('self', null=True, blank=True,
                            related_name='state', on_delete=models.CASCADE)
    
    def __str__(self):
        return "state[%s]{name:%s, status:%s}" % (self.id,
                                                  self.name, self.status)
