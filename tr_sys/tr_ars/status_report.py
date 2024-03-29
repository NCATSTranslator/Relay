from django.core import serializers
from .models import Agent, Message, Channel, Actor
import json, logging, statistics
import requests
import datetime
import traceback
import Levenshtein
from django.conf import settings

logger = logging.getLogger(__name__)

def prep_url(url):
    if url[-1] == "/":
        url = url[:-1]
    s = url.split("/")[2:]
    if ":" not in s[0]:
        if s[0].startswith("https:"):
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
    except Exception as e:
        logger.error("Unexpected error 1: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
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
        if(not a.active):
            continue
        del actor['fields']
        #actor['name'] = a.agent.name + '-' + a.path
        actor['channel'] = a.channel.name
        actor['agent'] = a.agent.name
        actor['remote'] = a.remote
        actor['path'] = req.build_absolute_uri(a.url())
        actor['messages'] = Message.objects.filter(actor=a.pk).count()
        actor_results = 'No message'
        for mesg in Message.objects.filter(actor=a.pk).order_by('-timestamp')[:1]:
            actor['latest'] = req.build_absolute_uri("/ars/api/messages/"+str(mesg.pk))
            message = Message.objects.get(pk=mesg.pk)
            if message.timestamp > response['messages']['latest']:
                actor['status'] = message.status
                for elem in Message.STATUS:
                    if elem[0] == actor['status']:
                        actor['status'] = elem[1]
            data = message.data
            if data is not None and 'message' in data and 'results' in data['message'] and data['message']['results'] is not None:
                actor_results = len(data['message']['results'])
            else:
                actor_results = 0
        if 'status' not in actor:
            actor['status'] = Message.STATUS[-1][1]
        actor_times = []
        for mesg in Message.objects.filter(actor=a.pk).order_by('-timestamp')[:3]:
            message = Message.objects.get(pk=mesg.pk)
            parent = Message.objects.get(pk=message.ref.pk)
            actor_times.append((message.timestamp - parent.timestamp).total_seconds())
        actor['results'] = actor_results
        actor['timings'] = 'Unknown'
        if len(actor_times)>0:
            actor['timings'] = str(statistics.mean(actor_times))[:6]
        response['actors'][a.agent.name + '-' + a.path] = actor

    # match SmartAPI entries to actors
    matched = dict()
    for actor in response['actors'].keys():
        # if remote ends in /query, remove that
        remote = response['actors'][actor]['remote']
        if remote[-6:] == '/query':
            remote = remote[:-6]
        bestmatch = None
        bestmatchserver = None
        bestmatchscore = 100
        bestmatchsources = ''
        for api in smartapis:
            if 'servers' in api:
                for server in api['servers']:
                    match = url_score(server['url'], remote)
                    if match < bestmatchscore:
                        bestmatch = api['_id']
                        bestmatchserver = server['url']
                        bestmatchscore = match
                        if bestmatch in smartresponse:
                            bestmatchsources = smartresponse[bestmatch]['sources']
                        else:
                            bestmatchsources = 'error'
        #if bestmatchscore == 0 or (bestmatch not in matched and bestmatchscore < 50):
        #print(bestmatchscore, bestmatchserver, remote)
        if bestmatchscore < 50 and (bestmatch not in matched.keys() or matched[bestmatch][0] > bestmatchscore):
            if bestmatchscore == 0:
                response['actors'][actor]['smartapi'] = "https://smart-api.info/api/metadata/" + bestmatch
                response['actors'][actor]['sources'] = bestmatchsources
                for api in smartapis:
                    if api['_id'] == bestmatch:
                        response['actors'][actor]['smartapireasonercompliant'] = reasoner_compliant(api)
            else:
                response['actors'][actor]['smartapi'] = "Unknown"
                response['actors'][actor]['smartapiguess'] = "https://smart-api.info/api/metadata/" + bestmatch
                response['actors'][actor]['smartapiserver'] = bestmatchserver
            if bestmatch in matched.keys():
                response['actors'][matched[bestmatch][1]]['smartapi'] = 'Unknown'
            matched[bestmatch] = [bestmatchscore, actor]
        else:
            response['actors'][actor]['smartapi'] = "Unknown"

    queue_status = 0 # message queue might be down
    if 'latest' in response['messages']:
        tz_info = latest.timestamp.tzinfo
        diff = datetime.datetime.now(tz_info)-latest.timestamp
        if diff.total_seconds() < 3:
            queue_status = 1 # latest is too recent to test whether message queue is down
        response['messages']['latest'] = str(latest.timestamp)

    for key in response['actors'].keys():
        actor = response['actors'][key]
        #('D', 'Done'),
        #('S', 'Stopped'),
        #('R', 'Running'),
        #('E', 'Error'),
        #('W', 'Waiting'),
        #('U', 'Unknown')
        if actor['status'] not in ['Unknown', 'Error']:
            queue_status = 2 # message queue is up (as of the last message posted to the queue)
        if actor['status'] in ['Running', 'Done']:
            actor['statusicon'] = 'status2'
            actor['statusiconcomment'] = 'up'
        elif actor['status'] in ['Waiting']:
            actor['statusicon'] = 'status1'
            actor['statusiconcomment'] = 'Service waiting'
        elif actor['status'] in ['Error']:
            actor['statusicon'] = 'status8'
            actor['statusiconcomment'] = 'Service error'
        elif actor['status'] in ['Stopped']:
            actor['statusicon'] = 'status9'
            actor['statusiconcomment'] = 'Service stopped'
        else:
            actor['statusicon'] = 'status0'
            actor['statusiconcomment'] = 'Service outage'

    page = dict()
    page['ARS'] = response
    page['ARS-Queue-Status'] = queue_status
    if queue_status == 0:
        for key in response['actors'].keys():
            actor = response['actors'][key]
            actor['statusiconcomment'] = ''

    arsreasonsers = dict()
    reasoners = dict()
    others = dict()
    for key in smartresponse.keys():
        if key in matched:
            arsreasonsers[key] = smartresponse[key]
        elif smartresponse[key]['smartapireasonercompliant'] == True:
            reasoners[key] = smartresponse[key]
        else:
            others[key] = smartresponse[key]
    page['SmartAPI'] = dict()
    page['SmartAPI']['ARS-Reasoners'] = arsreasonsers
    page['SmartAPI']['Other-Reasoners'] = reasoners
    page['SmartAPI']['Other-Translator-SmartAPIs'] = others
    return page

def status_smartapi():
    #https://smart-api.info/api/query/?q=translator&fields=tags.name%2Cservers%2Cinfo.description%2Cinfo.title&size=200
    #https://smart-api.info/api/metadata/a85f096bd4120ba065b2f25ffb68dcb0
    base_dir = settings.BASE_DIR
    response = dict()
    #smartapis = requests.get("https://smart-api.info/api/query/?q=translator&size=200").json()
    smartapis = json.load(open(base_dir+"/tr_ars/SmartAPI-Translator.json"))
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
        api['timestamp'] = entry['_meta']['last_updated']
        servers = []
        if 'servers' in entry:
            for item in entry['servers']:
                servers.append(item['url'])
        api['servers'] = servers
        api['smartapireasonercompliant'] = reasoner_compliant(entry)
        api['entities'] = []
        sources = []
        if 'components' in entry:
            if 'x-bte-kgs-operations' in entry['components']:
                for key, item in entry['components']['x-bte-kgs-operations'].items():
                    if isinstance(item, list):
                        for item2 in item:
                            if 'source' in item2 and item2['source'] not in sources:
                                sources.append(item2['source'])
                    else:
                        if 'source' in item and item['source'] not in sources:
                            sources.append(item['source'])

            if 'x-bte-response-mapping' in entry['components']:
                for key, item in entry['components']['x-bte-response-mapping'].items():
                    if isinstance(item, dict):
                        for key2 in item.keys():
                            if '$source' in item[key2] and item[key2]['$source'] not in sources:
                                sources.append(item[key2]['$source'])
        api['sources'] = ", ".join(sources)

        if 'tags' in entry:
            trans = False
            for tag in entry['tags']:
                if tag['name'].lower() == 'translator':
                    trans = True
                if tag['name'].lower() == 'trapi':
                    trans = True
            if trans:
                response[entry['_id']] = api
    return response, smartapis['hits']

def status(req):
    response = dict()
    smartresponse, smartapis = status_smartapi() #TODO pull new info upon RSS feed notification
    response = status_ars(req, smartresponse, smartapis)

    return response

    #TODO https://smart-api.info/api/metakg
    #https://api.bte.ncats.io/metakg?provided_by=drugbank
