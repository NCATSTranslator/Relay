from django.contrib import admin

# Register your models here.
from .models import Agent, Channel, Actor, State

admin.site.register(Agent)
admin.site.register(Channel)
admin.site.register(Actor)
admin.site.register(State)
