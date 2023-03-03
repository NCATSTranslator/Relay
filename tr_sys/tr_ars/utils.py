import copy
import json
import logging
import traceback
import requests
import urllib
import statistics
import sys
from .models import Agent, Message, Channel, Actor
from scipy.stats import rankdata
from celery import shared_task
from celery import task
from tr_sys.celery import app
import typing

#NORMALIZER_URL='https://nodenormalization-sri.renci.org/1.2/get_normalized_nodes?'
NORMALIZER_URL='https://nodenormalization-sri.renci.org/1.3/get_normalized_nodes'

class QueryGraph():
    def __init__(self,qg):
        if qg==None:
            return None
        self.__rawGraph = qg
        self.__nodes =  qg['nodes']
        self.__edges = qg['edges']
    def getEdges(self):
        return self.__edges
    def getNodes(self):
        return self.__nodes
    def getAllCuries(self):
        nodes = self.getNodes()
        curies =[]
        for node in nodes:
            if("curie") in node:
                curies.append(node['curie'])
        return curies
    def getRawGraph(self):
        return self.__rawGraph
    def __json__(self):
        return json.dumps(self.getRawGraph())

class KnowledgeGraph():
    def __init__(self,kg):
        if kg == None:
            return None
        self.rawGraph = kg
        self.__nodes=kg['nodes']
        self.__edges = kg['edges']
    def getEdges(self):
        return self.__edges
    def getNodes(self):
        return self.__nodes
    def getAllIds(self):
        nodes=self.getNodes()
        ids = []
        for node in nodes:
            ids.append(node)
        return ids
    def getNodeById(self,id):
        nodes = self.getNodes()
        node = nodes.get(id)
        return node
    def getRaw(self):
        return self.rawGraph

    def getEdgeById(self,id):
        edges=self.getEdges()
        edge = edges.get(id)
        return edge
    def __json__(self):
        return json.dumps(self.getRaw())

#TODO make this a proper object, list of Result objects
class Results():
    def __init__(self,results):
        if results == None:
            return None
        self.__results=results
    def getEdgeBindings(self):
        edgeBindings=[]
        for result in self.__results:
            try:
                bindings = result['edge_bindings']
                edgeBindings.append(bindings)
            except Exception as e:
                logging.error("Unexpected error 3: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))

        return edgeBindings
    def getNodeBindings(self):
        nodeBindings=[]
        for result in self.__results:
            nodeBindings.append(result['node_bindings'])
        return nodeBindings
    def getRaw(self):
        return self.__results
class Result():
    def __init__(self,result):
        self.__nodeBindings = result['node_bindings']
        self.__edgeBindings = result['edge_bindings']
    def getEdgeBindings(self):
        return self.__edgeBindings
    def getNodeBindings(self):
        return self.__nodeBindings

class TranslatorMessage():
    def __init__(self,message):
        if "results" in message:
            self.__results = Results(message['results'])
        else:
            self.__results = None

        if "knowledge_graph" in message:
            self.__kg=KnowledgeGraph(message['knowledge_graph'])
        else:
            self.__kg=None

        if "query_graph" in message:
            self.__qg=QueryGraph(message['query_graph'])
        else:
            self.__qg=None
        self.__sharedResults = None

    def getResults(self):
        return self.__results
    def getQueryGraph(self):
        return self.__qg
    def getKnowledgeGraph(self):
        return self.__kg
    def getSharedResults(self):
        return self.__sharedResults
    #returns a set of sets of triples representing results
    def getResultTuples(self):
        results = self.getResults()
        kg = self.getKnowledgeGraph()
        resultTuples=set()
        for eb in results.getEdgeBindings():
            tuples=set()
            for bindings in eb.values():
                for binding in bindings:
                    #id = binding['kg_id']
                    edge = kg.getEdgeById(binding["id"])
                    source = edge['subject']
                    type = edge['predicate']
                    target = edge['object']
                    tuple = (source,type,target)
                    tuples.add(tuple)
            resultTuples.add(frozenset(tuples))
        return resultTuples
    def getResultNodeSets(self):
        results = self.getResults()
        nodeSets=[]
        if results is None:
            return None
        nodeb = results.getNodeBindings()
        kg = self.getKnowledgeGraph()
        for bindings in nodeb:
            nodes = set()
            for nodeid in bindings.keys():
                binding=bindings.get(nodeid)
                if len(binding)>1:
                    logging.debug("Multiple bindings found for a single node")
                else:
                    binding=binding[0]
                #node = kg.getNodeById(binding["id"]) can we just add the binding id and count on it to be the CURIE?
                nodes.add(binding["id"])
            nodeSets.append(frozenset(nodes)) #this needs to be a frozen set so it's hashable later
        return nodeSets
    def getResultMap(self):
        map = {}
        results=self.getResults()
        if results is not None:
            results = results.getRaw()
        else:
            return None
        for result in results:
            nodes = set()
            nb = result["node_bindings"]
            for nodeid in nb.keys():
                binding=nb.get(nodeid)
                if len(binding)>1:
                    logging.debug("Multiple bindings found for a single node")
                else:
                    binding=binding[0]
                    nodes.add(binding["id"])
            map[frozenset(nodes)]=result
        return map

    def setQueryGraph(self,qg):
        self.__qg=qg
    def setKnowledgeGraph(self,kg):
        self.__kg=kg
    def setResults(self,results):
        self.__results=results
    def setSharedResults(self,sharedResults):
        self.__sharedResults=sharedResults
    def to_dict(self):
        d={}
        if self.getQueryGraph() is not None:
            qg= self.getQueryGraph()
            d['query_graph']=self.getQueryGraph().getRawGraph()
        else:
            d['query_graph']={}
        if self.getKnowledgeGraph() is not None:
            d['knowledge_graph']=self.getKnowledgeGraph().rawGraph
        else:
            d['knowledge_graph']={}
        if self.getResults() is not None:
            d['results']=self.getResults().getRaw()
        else:
            d['results']={}

        return {"message":d} #need to wrap all this in "message:"
    def __json__(self):
        return self.to_dict()

def getCommonNodeIds(messageList):
    if len(messageList)==0:
        return set()
    idSet = set(messageList[0].getKnowledgeGraph().getAllIds())
    commonSet =set()
    for msg in messageList[1:]:
        currentSet = set(msg.getKnowledgeGraph().getAllIds())
        inter = currentSet.intersection(idSet)
        commonSet.update(inter)
        idSet.update(currentSet)

    return commonSet

def getCommonNodes(messageList):
    commonMap ={}
    commonIds = getCommonNodeIds(messageList)
    for mesg in messageList:
        kg= mesg.getKnowledgeGraph()
        for id in commonIds:
            kgNode = kg.getNodeById(id)
            if kgNode is not None:
                if id not in commonMap:
                    commonMap[id]=[kgNode]
                else:
                    commonMap[id].append(kgNode)

    return commonMap



def mergeMessages(messageList):
    messageListCopy = copy.deepcopy(messageList)
    message = messageListCopy.pop()
    merged = mergeMessagesRecursive(message,messageListCopy)

    return merged

def mergeMessagesRecursive(mergedMessage,messageList):
    #need to clean things up and average our normalized scores now that they're all in

    if len(messageList)==0:
        try:
            results = mergedMessage.getResults()
            if results is not None:
                results = results.getRaw()
                for result in results:
                    if "normalized_score" in result.keys():
                        ns = result["normalized_score"]
                        if isinstance(ns,list) and len(ns)>0:
                            result["normalized_score"]= sum(ns) / len(ns)
        except Exception as e:
            logging.debug(e.__traceback__)

        mergedMessage.status='Done'
        mergedMessage.code = 200
        return mergedMessage
    else:
        currentMessage = messageList.pop()
        #merge Knowledge Graphs
        mergedKnowledgeGraph = mergeKnowledgeGraphs(currentMessage.getKnowledgeGraph(),mergedMessage.getKnowledgeGraph())
        #merge Results
        currentResultMap= currentMessage.getResultMap()
        mergedResultMap=mergedMessage.getResultMap()
        mergedResults=mergeDicts(currentResultMap,mergedResultMap)



        values = mergedResultMap.values()
        newResults= Results(list(values))
        mergedMessage.setResults(newResults)
        mergedMessage.setKnowledgeGraph(mergedKnowledgeGraph)
        return mergeMessagesRecursive(mergedMessage,messageList)


def mergeDicts(dcurrent,dmerged):
    for key in dcurrent.keys():
        cv=dcurrent[key]
        #print("key is "+str(key))
        if key in dmerged.keys():
            mv=dmerged[key]
            if (isinstance(cv,dict) and isinstance(mv,dict)):
                #print("merging dicts")
                dmerged[key]=mergeDicts(cv,mv)
            elif isinstance(mv,list) and not isinstance(cv,list):
                mv.append(cv)
            elif isinstance(mv,list) and isinstance(cv,list):
                try:
                    #if they're both lists, we have to shuffle
                    #print("shuffling")
                    #let's check for the special case of lists of dicts with ids (e.g. 'gene' for a node binding)
                    if (all(isinstance(x, dict) for x in mv)
                        and all(isinstance(y, dict) for y in cv)):
                        cmap={}
                        mmap={}
                        for cd in cv:
                            if "id" in cd.keys():
                                cmap[cd["id"]]=cd
                            else:
                                logging.debug("list item lacking id? "+str(cd))
                        for md in mv:
                            if "id" in md.keys():
                                mmap[md["id"]]=md
                            else:
                                logging.debug("list item lacking id? "+str(cd))

                        for ck in cmap.keys():
                            if ck in mmap.keys():
                                mmap[ck]=mergeDicts(cmap[ck],mmap[ck])
                            else:
                                mmap[ck]=cmap[ck]
                        dmerged[key]=list(mmap.values())

                    #if they're at least hashable, we combine without duplicates
                    elif(all(isinstance(x, typing.Hashable) for x in mv)
                         and all(isinstance(y, typing.Hashable) for y in cv)):

                        dmerged[key]=mv+list(set(cv)-set(mv))
                    #if they're not even hashable, we just combine them like when you make scrambled eggs because you messed up an omlette
                    else:
                        dmerged[key]=mv+cv

                except Exception as e:
                    print(e)
            else:
                #print("newly listing")
                try:
                    if ((isinstance(mv, typing.Hashable)
                    and isinstance(cv, typing.Hashable)
                    and mv==cv) or cv is None):
                        continue
                    else:
                        dmerged[key]=[mv,cv]
                except Exception as e:
                    print(e)
        else:
            #print("adding new")
            dmerged[key]=cv
        #print("value is now "+str(dmerged[key]))
    return dmerged


def mergeResults(r1, r2):
    return Results(r1.getRaw()+r2.getRaw())
def mergeKnowledgeGraphs(kg1, kg2):
    #mergedNodes = []
    mergedNodes ={}
    firstIds = set(kg1.getAllIds())
    try:
        idTest = kg2.getAllIds()
        secondIds = set(idTest)
    except Exception as e:
        logging.error("Unexpected error 4: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
    intersection = firstIds.intersection(secondIds)
    firstOnly = firstIds.difference(secondIds)
    secondOnly = secondIds.difference(firstIds)
    for id in firstOnly:
        mergedNodes[id]=kg1.getNodeById(id)
    for id in secondOnly:
        mergedNodes[id]=kg2.getNodeById(id)
    for id in intersection:
        mergedNode = {}
        firstNode = kg1.getNodeById(id)
        secondNode = kg2.getNodeById(id)
        firstKeySet =set(firstNode.keys())
        secondKeySet = set(secondNode.keys())
        keyIntersection = firstKeySet.intersection(secondKeySet)
        firstOnlyKeys=firstKeySet.difference(secondKeySet)
        secondOnlyKeys=secondKeySet.difference(firstKeySet)
        for key in firstOnlyKeys:
            mergedNode[key]=firstNode.get(key)
        for key in secondOnlyKeys:
            mergedNode[key]=secondNode.get(key)
        for key in keyIntersection:
            if firstNode.get(key)!= secondNode.get(key):
                mergedNode[key]=[firstNode.get(key),secondNode.get(key)]
            else:
                mergedNode[key]=firstNode.get(key)
            mergedNodes[id]=mergedNode

    #Since edges don't have the same guarantee of identifiers matching as nodes, we'll just combine them naively and
    #eat the redundancy if we have two functionally identical edges for now]
    test =kg1.getEdges()
    mergedEdges=kg1.getEdges()|kg2.getEdges()
    mergedKg={
        "nodes":mergedNodes,
        "edges":mergedEdges
    }
    return KnowledgeGraph(mergedKg)

def sharedResultsJson(sharedResultsMap):
    results=[]
    sharedResultsMap={k: v for k, v in sorted(sharedResultsMap.items(), key=lambda item: item[1],reverse=True)}
    for k,v in sharedResultsMap.items():
        tuples=[]
        for tuple in k:
            pass
            tupleDict = {
                "source":tuple[0],
                "relation":tuple[1],
                "target":tuple[2]
            }
            tuples.append(tupleDict)
        result = {
            "results":tuples,
            "count":v
        }
        results.append(json.dumps(result,indent=2))
    return results

def keys_exist(element, *keys):
    if not isinstance(element, dict):
        raise AttributeError('keys_exists() expects dict as first argument.')
    if len(keys) == 0:
        raise AttributeError('keys_exists() expects at least two arguments, one given.')

    _element = element
    for key in keys:
        try:
            _element = _element[key]
            if _element is None:
                return False
        except KeyError:
            return False
    return True

def get_safe(element,*keys):
    '''
    :param element: JSON to be processed
    :param keys: list of keys in order to be traversed. e.g. "fields","data","message","results
    :return: the value of the terminal key if present or None if not
    '''
    if element is None:
        return None
    _element = element
    for key in keys:
        try:
            _element = _element[key]
            if _element is None:
                return None
            if key == keys[-1]:
                return _element
        except KeyError:
            return None
    return None

'''
Takes a CURIE and returns the canonical CURIE from the node normalizer or returns the original CURIE if none is found
'''
def canonize(curies):

    # urllib.urlencode([('var', 'earth'), ('var', 'wind')])
    # 'var=earth&var=wind'
    if not isinstance(curies,list):
        curies = [curies]
    tuple_list=[]
    j ={
        "curies":curies,
        "conflate":True
    }
    r = requests.post(NORMALIZER_URL,json.dumps(j))
    rj=r.json()
    return rj


def canonizeResults(results):
    canonical_results=[]
    for result in results:
        canonical_result=set
        node_bindings = result.getNodeBindings()
        for binding in node_bindings:
            curie = get_safe(binding,"id")
            canonical=canonize(curie)
            canonical_result.append(canonical)
        canonical_results.append(frozenset(canonical_result))
    return canonical_results

def canonizeKnowledgeGraph(kg):
    nodes = kg.getNodes()
    ids = list(nodes.keys())
    if len(ids)>0:
        canonical = canonize(ids)


def canonizeMessageTest(kg,results):

    nodes = kg['nodes']
    edges = kg['edges']
    ids=list(nodes.keys())
    if len(ids)>0:
        canonical = canonize(ids)
        changes = {}
        for key,value in canonical.items():
            if value is not None and key != value["id"]["identifier"]:
                changes[key]=value
        bindings=[res['node_bindings'] for res in results]
        for binding in bindings:
            for key in binding.keys():
                id_list = binding[key]
                for id_dict in id_list:
                    if id_dict['id'] in changes:
                        id_dict['id']=changes[id_dict['id']]['id']['identifier']
        for change in changes:
            if change in nodes:
                new_id = changes[change]['id']['identifier']
                print("Changing "+(str(change))+" to "+str(new_id))
                nodes[new_id]=nodes.pop(change)
                original_node={
                            "attribute_type_id": "biolink:xref",
                            "original_attribute_name": "original_id",
                            "value": change,
                            "value_type_id": "metatype:String",
                            "attribute_source": None,
                            "value_url": None,
                            "description": None,
                }
                attributes = nodes[new_id]['attributes']
                if isinstance(attributes, list):
                    attributes.append(original_node)
                else:
                    nodes[new_id]['attributes'] = [original_node]

        for change in changes:
            for edge_key,edge_value in edges.items():
                for key,value in edge_value.items():
                    if change == value:
                        new_id = changes[change]['id']['identifier']
                        edges[edge_key][key] = new_id

    return kg, results


def canonizeMessage(msg):
    #kg = msg.getKnowledgeGraph()
    nodes = msg.getKnowledgeGraph().getNodes()
    ids=list(nodes.keys())
    if len(ids)>0:
        canonical = canonize(ids)
        #changes= copy.deepcopy(canonical)'
        changes = {}
        for key,value in canonical.items():
            if value is not None and key != value["id"]["identifier"]:
                changes[key]=value
        results = msg.getResults()
        bindings = results.getNodeBindings()
        for binding in bindings:
            for key in binding.keys():
                id_list = binding[key]
                for id_dict in id_list:
                    if id_dict['id'] in changes:
                        #print("Changing "+str(id_dict['id'])+" to "+ str(changes[id_dict['id']]['id']['identifier'])+" at "+str(bindings.index(binding)))
                        id_dict['id']=changes[id_dict['id']]['id']['identifier']
        for change in changes:
            if change in nodes:
                new_id = changes[change]['id']['identifier']
                #print("Changing "+(str(change))+" to "+str(new_id))
                nodes[new_id]=nodes.pop(change)

def findSharedResults(sharedResults,messageList):
    canonicalResults=[]
    for message in messageList:
        results = canonizeResults(message.getResults())
        canonicalResults.append(results)

def ScoreStatCalc(results):
    stat={}
    if results is not None and len(results)>0:
        scoreList = [d['score'] for d in results if 'score' in d]
        if len(scoreList) == 0:
            return stat
        stat['median'] = statistics.median(scoreList)
        stat['mean'] = statistics.mean(scoreList)
        stat['stdev'] = statistics.stdev(scoreList)
        stat['minimum'] = min(scoreList)
        stat['maximum'] = max(scoreList)

    return stat

def normalizeScores(results):
    if results is not None and len(results)>0:
        scoreList = [d['score'] for d in results if 'score' in d]
        ranked = list(rankdata(scoreList)*100/len(scoreList))
        if(len(ranked)!=len(scoreList)):
            logging.debug("Score normalization aborted.  Score list lengths not equal")
            return results
        if ranked:
            for result in results:
                result["normalized_score"]=ranked.pop(0)
    return results

def getChildrenFromParent(pk):
    children = Message.objects.filter(ref__pk=pk)
    messageList=[]
    if children is not None:
        for child in children:
            childPk=child.id
            messageList.append(Message.objects.get(pk=childPk))
    return messageList

def createMessage(actor):
    message = Message.create(code=202, status='Running', data={},
                             actor=actor)
    message.save()
    return message


@app.task(name="merge")
def merge(pk,merged_pk):
    messageList= getChildrenFromParent(pk)
    mergedComplete = Message.objects.get(pk=merged_pk)

    newList =[]
    for message in messageList:
        mesg=get_safe(message.to_dict(),"fields","data","message")
        if mesg is not None:
            t_mesg=TranslatorMessage(message.to_dict()["fields"]["data"]["message"])
        else:
            continue
        if t_mesg.getKnowledgeGraph() is not None:
            #temporarily removing canonization for testing as I pre-normalized for performance
            #b4f4e046-db06-4f6b-b4ae-b153e79fb18b
            #TODO uncomment before committing!
            canonizeMessage(t_mesg)
            newList.append(t_mesg)

    merged = mergeMessages(newList)
    mergedComplete.data=merged.to_dict()
    mergedComplete.code = 200
    mergedComplete.status = 'D'
    mergedComplete.save()

def hop_level_filter(results, hop_limit):

    filtered_result = list(filter(lambda result: (len(result['node_bindings'].keys())) < hop_limit, results))
    return filtered_result

def score_filter(results, range):

    norm_score_results = list(filter(lambda result: result.get('normalized_score') != None, results))
    filtered_result = list(filter(lambda result: range[0] < result["normalized_score"] < range[1], norm_score_results))
    return filtered_result

def node_type_filter(kg_nodes, results, forbidden_category):

    forbidden_nodes=[]
    for node, value in kg_nodes.items():
        present_category=[]
        for entity in value['categories']:
            if 'biolink:' in entity:
                present_category.append(entity.split(':')[1])
            else:
                present_category.append(entity)
        if any(item in forbidden_category for item in present_category):
            forbidden_nodes.append(node)

    for result in list(results):
        ids=[]
        for res_node, res_value in result['node_bindings'].items():
            for val in res_value:
                ids.append(str(val['id']))
        if any(item in ids for item in forbidden_nodes):
            results.remove(result)
    return results

def specific_node_filter(results, forbbiden_node):
    for result in list(results):
        ids=[]
        for res_node, res_value in result['node_bindings'].items():
            for val in res_value:
                ids.append(str(val['id']))
        if any(item in ids for item in forbbiden_node):
            results.remove(result)
    return results

