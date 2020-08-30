from django.core import serializers
from .models import Agent, Message, Channel, Actor
import json, logging
import requests
import Levenshtein

logger = logging.getLogger(__name__)

def prep_url(url):
    if url[-1] == "/":
        url = url[:-1]
    s = url.split("/")[2:]
    if ":" not in s[0]:
        if s[0].startswith("http3:"):
            s[0] = s[0] + ":443"
        else:
            s[0] = s[0] + ":80"
    ser, port = s[0].split(":")
    del s[0]
    sser = ser.split(".")
    ser = []
    for i in range(len(sser)):
        ser.insert(0, sser[i])
    return ser, port, s

def url_score(remote, server):
    s1, port1, path1 = prep_url(remote)
    s2, port2, path2 = prep_url(server)
    while len(s1) < len(s2):
        if len(s2[len(s1)]) > 3:
            s2[len(s1)] = s2[len(s1)][:3]
        s1.append('')
    while len(s2) < len(s1):
        if len(s1[len(s2)]) > 3:
            s1[len(s2)] = s1[len(s2)][:3]
        s2.append('')
    s1.append(port1)
    s2.append(port2)
    for i in range(min(len(path1), len(path2))):
        s1.append(path1[i])
        s2.append(path2[i])
    score = 0.
    for i in range(len(s1)):
        if len(s2) > i:
            dist = (10-i)*(10-i)/10*Levenshtein.distance(s1[i], s2[i])
            score = score + dist
    return score

def reasoner_compliant(api):
    try:
        for entry in api['paths']:
            if entry['path'].find('/query') > -1:
                path = entry['pathitem']
                if path['post']['requestBody']['content']['application/json']['schema']['$ref'].find('schemas/Query') > -1:
                    return True
    except:
        pass
    return False

def status_ars(req, smartresponse, smartapis):
    response = dict()
    response['messages'] = dict()
    response['messages']['submitted'] = Message.objects.filter(ref=None).count()
    response['messages']['responses'] = Message.objects.count()-response['messages']['submitted']
    for mesg in Message.objects.filter(ref=None).order_by('-timestamp')[:1]:
        latest = Message.objects.get(pk=mesg.pk)
        response['messages']['latest_message'] = req.build_absolute_uri("/ars/api/messages/"+str(latest.pk)+"?trace=y")
        response['messages']['latest'] = latest.timestamp

    response['actors_count'] = Actor.objects.count()-1
    response['actors'] = dict()
    for a in Actor.objects.exclude(path__exact=''):
        actor = json.loads(serializers.serialize('json', [a]))[0]
        del actor['fields']
        #actor['name'] = a.agent.name + '-' + a.path
        actor['channel'] = a.channel.name
        actor['agent'] = a.agent.name
        actor['remote'] = a.remote
        actor['path'] = req.build_absolute_uri(a.url())
        actor['messages'] = Message.objects.filter(actor=a.pk).count()
        for mesg in Message.objects.filter(actor=a.pk).order_by('-timestamp')[:1]:
            actor['latest'] = req.build_absolute_uri("/ars/api/messages/"+str(mesg.pk))
            message = Message.objects.get(pk=mesg.pk)
            if message.timestamp > response['messages']['latest']:
                actor['status'] = message.status
                for elem in Message.STATUS:
                    if elem[0] == actor['status']:
                        actor['status'] = elem[1]
        if 'status' not in actor:
            actor['status'] = Message.STATUS[-1][1]
        actor_results = []
        actor_times = []
        for mesg in Message.objects.filter(actor=a.pk).order_by('-timestamp')[:10]:
            message = Message.objects.get(pk=mesg.pk)
            data = message.data
            if 'results' in data:
                actor_results.append(len(data['results']))
            else:
                actor_results.append(0)
            parent = Message.objects.get(pk=message.ref.pk)
            actor_times.append(str(message.timestamp - parent.timestamp))
        actor['results'] = actor_results
        actor['timings'] = actor_times
        response['actors'][a.agent.name + '-' + a.path] = actor

    if 'latest' in response['messages']:
        response['messages']['latest'] = str(latest.timestamp)

    # match SmartAPI entries to actors
    matched = []
    for actor in response['actors'].keys():
        bestmatch = None
        bestmatchserver = None
        bestmatchscore = 100
        for api in smartapis:
            for server in api['servers']:
                match = url_score(server['url'], response['actors'][actor]['remote'])
                if match < bestmatchscore:
                    bestmatch = api['_id']
                    bestmatchserver = server['url']
                    bestmatchscore = match
        if bestmatchscore == 0 or (bestmatch not in matched and bestmatchscore < 50):
            if bestmatchscore == 0:
                response['actors'][actor]['smart-api'] = "https://smart-api.info/api/metadata/" + bestmatch
                for api in smartapis:
                    if api['_id'] == bestmatch:
                        response['actors'][actor]['smart-api-reasoner-compliant'] = reasoner_compliant(api)
            else:
                response['actors'][actor]['smart-api'] = "Unknown"
                response['actors'][actor]['smart-api-guess'] = "https://smart-api.info/api/metadata/" + bestmatch
                response['actors'][actor]['smart-api-server'] = bestmatchserver
            matched.append(bestmatch)
        else:
            response['actors'][actor]['smart-api'] = "Unknown"

    page = dict()
    page['ARS'] = response

    arsreasonsers = dict()
    reasoners = dict()
    others = dict()
    for key in smartresponse.keys():
        if key in matched:
            arsreasonsers[key] = smartresponse[key]
        elif smartresponse[key]['smart-api-reasoner-compliant'] == True:
            reasoners[key] = smartresponse[key]
        else:
            others[key] = smartresponse[key]
    page['SmartAPI'] = dict()
    page['SmartAPI']['ARS-Reasoners'] = arsreasonsers
    page['SmartAPI']['Other-Reasoners'] = reasoners
    page['SmartAPI']['Other-Translator-SmartAPIs'] = others
    return page

def status_smartapi():
    response = dict()
    smartapis = requests.get("https://smart-api.info/api/query/?q=translator&size=200").json()
    #smartapis = json.load(open("tr_sys/tr_ars/SmartAPI-Translator.json"))
    for entry in smartapis["hits"]:
        api = dict()
        api['id'] = "https://smart-api.info/api/metadata/" + entry['_id']
        api['title'] = str(len(response.keys()))
        if 'title' in entry['info']:
            api['title'] = entry['info']['title']
        if 'version' in entry['info']:
            api['title'] = api['title'] + " (v" + entry['info']['version'] + ")"
        api['contact'] = ""
        if 'contact' in entry['info']:
            api['contact'] = entry['info']['contact']
        api['timestamp'] = entry['_meta']['timestamp']
        servers = []
        for item in entry['servers']:
            servers.append(item['url'])
        api['servers'] = servers
        api['smart-api-reasoner-compliant'] = reasoner_compliant(entry)
        api['entities'] = []

        if 'tags' in entry:
            trans = False
            for tag in entry['tags']:
                if tag['name'].lower() == 'translator':
                    trans = True
                if tag['name'].lower() == 'reasoner':
                    trans = True
            if trans:
                response[entry['_id']] = api
    return response, smartapis['hits']

def status(req):
    response = dict()
    smartresponse, smartapis = status_smartapi() #TODO pull new info upon RSS feed notification
    response = status_ars(req, smartresponse, smartapis)

    return response
