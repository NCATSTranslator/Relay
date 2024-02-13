import copy
import json
import logging
import traceback
import os, sys
from datetime import time, datetime
from django.db import transaction
import requests
import statistics
from .api import get_ars_actor, get_or_create_actor
from . import scoring
from .models import Message, Channel
from scipy.stats import rankdata
from celery import shared_task
from tr_sys.celery import app
import typing
import time as sleeptime
import re
from objsize import get_deep_size
from django.shortcuts import get_object_or_404
from .scoring import compute_from_results
from collections import Counter


ARS_ACTOR = {
    'channel': [],
    'agent': {
        'name': 'ars-ars-agent',
        'uri': ''
    },
    'path': '',
    'inforesid': 'ARS'
}

NORMALIZER_URL=os.getenv("TR_NORMALIZER") if os.getenv("TR_NORMALIZER") is not None else "https://nodenormalization-sri.renci.org/1.4/get_normalized_nodes"
ANNOTATOR_URL=os.getenv("TR_ANNOTATOR") if os.getenv("TR_ANNOTATOR") is not None else "https://biothings.ncats.io/annotator/"
APPRAISER_URL=os.getenv("TR_APPRAISE") if os.getenv("TR_APPRAISE") is not None else "http://localhost:9096/get_appraisal"


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

        if "auxiliary_graphs" in message:
            self.__ag=message['auxiliary_graphs']
        else:
            self.__ag=None
        self.__sharedResults = None

    def getResults(self):
        return self.__results
    def getQueryGraph(self):
        return self.__qg
    def getKnowledgeGraph(self):
        return self.__kg
    def getAuxiliaryGraphs(self):
        return self.__ag
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
        if self.getAuxiliaryGraphs() is not None:
            d['auxiliary_graphs']=self.getAuxiliaryGraphs()
        else:
            d['auxiliary_graphs']={}

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



def mergeMessages(messageList,pk):
    messageListCopy = copy.deepcopy(messageList)
    message = messageListCopy.pop()
    merged = mergeMessagesRecursive(message,messageListCopy, pk)

    return merged

def mergeMessagesRecursive(mergedMessage,messageList,pk):
    #need to clean things up and average our normalized scores now that they're all in
    logging.info(f'Merging new pk: {pk} recursively.  Currently {str(len(messageList))} messages left in the queue')
    logging.info(f'Current messages list in the queue: {messageList}')
    if len(messageList)==0:
        try:
            results = mergedMessage.getResults()
            if results is not None:
                logging.info(f'Averaing normalized scores for {pk}')
                try:
                    results = results.getRaw()
                    for result in results:
                        if "normalized_score" in result.keys():
                            ns = result["normalized_score"]
                            if isinstance(ns,list) and len(ns)>0:
                                result["normalized_score"]= sum(ns) / len(ns)
                        else:
                            logging.info('there is no normalized_score in result.keys()')
                except Exception as e:
                    print(e)
                    logging.debug(e.__traceback__)
        except Exception as e:
            logging.debug(e.__traceback__)
        if mergedMessage is not None:
            mergedMessage.status='Done'
            mergedMessage.code = 200
        else:
            logging.info(f'Merged Message was NoneType for : {pk}')
        return mergedMessage
    else:
        currentMessage = messageList.pop()
        #merge Knowledge Graphs

        #mergedKnowledgeGraph = mergeKnowledgeGraphs(currentMessage.getKnowledgeGraph(),mergedMessage.getKnowledgeGraph())
        logging.info(f'Merging knowledge graphs for {pk}')
        ckg = currentMessage.getKnowledgeGraph().getRaw()
        mkg = mergedMessage.getKnowledgeGraph().getRaw()
        mergedKnowledgeGraph = mergeDicts(ckg, mkg)
        logging.info(f'Merging knowledge graphs complete for {pk}')

        #merge Results
        logging.info(f'Merging results for {pk}')
        currentResultMap= currentMessage.getResultMap()
        mergedResultMap=mergedMessage.getResultMap()
        mergedResults=mergeDicts(currentResultMap,mergedResultMap)
        logging.info(f'Merging results complete for {pk}')

        #merge Aux Graphs
        logging.info(f'Merging aux graphs for {pk}')
        currentAux = currentMessage.getAuxiliaryGraphs()
        mergedAux=mergedMessage.getAuxiliaryGraphs()
        mergeDicts(currentAux,mergedAux)
        logging.info(f'Merging aux graphs complete for {pk}')


        logging.info(f'Merging: creating and converting for {pk}')

        values = mergedResultMap.values()
        newResults= Results(list(values))
        mergedMessage.setResults(newResults)
        mergedMessage.setKnowledgeGraph(KnowledgeGraph(mergedKnowledgeGraph))
        logging.info(f'Merging: creating and converting complete for {pk}')

        return mergeMessagesRecursive(mergedMessage,messageList,pk)


def mergeDicts(dcurrent,dmerged):
    if dcurrent is None:
        dcurrent = {}
    if dmerged is None:
        dmerged ={}
    for key in dcurrent.keys():
        cv=dcurrent[key]
        #print("key is "+str(key))
        if key in dmerged.keys():

            mv=dmerged[key]
            #analyses are a special case in which we just append them at the result level
            if key == 'analyses':
                dmerged[key]=mv+cv
                return dmerged
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
                                #logging.debug("list item lacking id? "+str(cd))
                                pass
                        for md in mv:
                            if "id" in md.keys():
                                mmap[md["id"]]=md
                            else:
                                #logging.debug("list item lacking id? "+str(cd))
                                pass

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
                    #instances in which we don't care
                    #1) They're the same thing
                    #2) Either one is None
                    if ((isinstance(mv, typing.Hashable)
                    and isinstance(cv, typing.Hashable)
                    and mv==cv) or cv is None
                    or mv is None):
                        continue
                    else:
                        if key == 'score':
                            del dmerged[key]
                            dmerged['scores']=[mv,cv]
                        elif key == 'query_ids':
                            dmerged['query_ids']=[mv,cv]
                        elif key == 'name':
                            #knowledge_graph->nodes->name can't be a list.  Fix this to add a new field later.
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
        raise e
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

def pre_merge_process(data,key, agent_name,inforesid):
    mesg = get_object_or_404(Message.objects.filter(pk=key))
    logging.info("Pre node norm for "+str(key))
    try:
        scrub_null_attributes(data)
    except Exception as e:
        logging.exception("Error in the scrubbing of null attributes")
        raise e
    try:
        normalize_nodes(data,agent_name,key)
        logging.info("node norm success for "+str(key))
    except Exception as e:
        post_processing_error(mesg,data,"Error in ARS node normalization")
        logging.exception("Error in ARS node normaliztion")
        raise e

    logging.info("Pre decoration for "+str(key))
    try:
        decorate_edges_with_infores(data,inforesid)
        logging.info("decoration success")
    except Exception as e:
        post_processing_error(mesg,data,"Error in ARS edge sources decoration\n"+e)
        logging.exception("Error in ARS edge source decoration")
        raise e
    logging.info("Normalizing scores for "+str(key))
    try:
        normalize_scores(mesg,data,key,agent_name)
    except Exception as e:
        post_processing_error(mesg,data,"Error in ARS score normalization")
        logging.exception("Error in ARS score normalization")
        raise e


def post_process(data,key, agent_name):
    code =200
    mesg = get_object_or_404(Message.objects.filter(pk=key))
    logging.info("Pre node annotation for agent %s pk: %s" % (agent_name, str(key)))
    try:
        annotate_nodes(mesg,data,agent_name)
        logging.info("node annotation successful for agent %s and pk: %s" % (agent_name, str(key)))
    except Exception as e:
        post_processing_error(mesg,data,"Error in annotation of nodes")
        logging.error("Error with node annotations for "+str(key))
        logging.exception("problem with node annotation post process function")
        raise e
    logging.info("pre scrub null for agent %s and pk %s" % (agent_name, str(key)))
    try:
        scrub_null_attributes(data)
    except Exception as e:
        logging.info("Problem with the second scrubbing of null attributes")
    logging.info("pre blocklist for "+str(key))
    try:
        remove_blocked(mesg, data)
    except Exception as e:
        logging.info(e.__cause__)
        logging.info("Problem with block list removal")
    logging.info("pre appraiser for agent %s and pk %s" % (agent_name, str(key)))
    try:
        appraise(mesg,data,agent_name)
        logging.info("appraiser successful for agent %s and pk %s" % (agent_name, str(key)))
    except Exception as e:
        code = 422
        results = get_safe(data,"message","results")
        default_ordering_component = {
            "novelty": 0,
            "confidence": 0,
            "clinical_evidence": 0
        }
        if results is not None:
            for result in results:
                if 'ordering_components' not in result.keys():
                    result['ordering_components']=default_ordering_component
                else:
                    continue
        else:
            logging.error('results returned from appraiser is None')

        #post_processing_error(mesg,data,"Error in appraiser")
        logging.error("Error with appraise for "+str(key))
        logging.exception("Error in appraiser post process function")
        #raise e
    try:
        results = get_safe(data,"message","results")
        if results is not None:
            new_res=scoring.compute_from_results(results)
            data['message']['results']=new_res
            logging.info("scoring succeeded for agent %s and pk %s" % (agent_name, key))
        else:
            logging.error('results from appraiser returns None, cant do the scoring')
        print()
    except Exception as e:
        post_processing_error(mesg,data,"Error in f-score calculation")
        logging.exception("Error in f-score calculation")
        raise e
    mesg.status='D'
    mesg.code=code
    mesg.save_compressed_dict(data)
    #mesg.data = data
    mesg.save()
def lock_merge(message):
    pass
    if message.merge_semaphore is True:
        return True
    else:
        message.merge_semaphore=True
        message.save(update_fields=['merge_semaphore'])
        return False

@shared_task(name="merge_and_post_process")
def merge_and_post_process(parent_pk,message_to_merge, agent_name, counter=0):

    logging.info(f"Starting merge for %s with parent PK: %s"% (agent_name,parent_pk))
    logging.info(f"Before atomic transaction for %s with parent PK: %s"% (agent_name,parent_pk))
    with transaction.atomic():
        parent = get_object_or_404(Message.objects.select_for_update().filter(pk=parent_pk))
        logging.info("the merge semaphore for agent %s is %s"% (agent_name, parent.merge_semaphore))
        lock_state = lock_merge(parent)
        logging.info("the lock state for agent %s is %s" % (agent_name, lock_state))
    transaction.commit()
    logging.info(f"After atomic transaction for %s with parent PK: %s"% (agent_name,parent_pk))

    if lock_state is False:
        try:
            logging.info(f"Before merging for %s with parent PK: %s"% (agent_name,parent_pk))
            merged = merge_received(parent,message_to_merge, agent_name)
            logging.info(f"After merging for %s with parent PK: %s"% (agent_name,parent_pk))
        except Exception as e:
            logging.info("Problem with merger for agent %s pk: %s " % (agent_name, (parent_pk)))
            logging.info(e, exc_info=True)
            logging.info('error message %s' % str(e))
            if merged is not None:
                merged.status='E'
                merged.code = 422
                merged.save()

    else:
        #If there is currently a merge happening, we wait until it finishes to do our merge
        if counter < 5:
            logging.debug("Merged_version locked for %s.  Attempt %s:" % (agent_name, str(counter)))
            sleeptime.sleep(5)
            counter = counter + 1
            merge_and_post_process(parent_pk,message_to_merge, agent_name, counter)
        else:
            logging.debug("Merging failed for %s %s" % (agent_name, str(parent_pk)))

    if merged is not None:
        try:
            logging.info('merged data for agent %s with pk %s is returned & ready to be preprocessed' % (agent_name, str(merged.id)))
            merged_data = merged.decompress_dict()
            post_process(merged_data,merged.id, agent_name)
            logging.info('post processing complete for agent %s with pk %s is returned & ready to be preprocessed' % (agent_name, str(merged.id)))

        except Exception as e:
            logging.info("Problem with post processing for agent %s pk: %s " % (agent_name, (parent_pk)))
            logging.info(e, exc_info=True)
            logging.info('error message %s' % str(e))
            merged.status='E'
            merged.code = 422
            merged.save()

def remove_blocked(mesg, data, blocklist=None):
    try:
        #logging.info("Getting the length of the dictionary in {} bytes".format(get_deep_size(data)))
        if blocklist is None:
            path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "blocklist.json")
            f = open(path)
            blocklist = json.load(f)
        #blocked_version = createMessage(get_ars_actor())
        #data=mesg.data
        results = get_safe(data,"message","results")
        nodes = get_safe(data,"message","knowledge_graph","nodes")
        edges = get_safe(data,"message","knowledge_graph","edges")
        aux_graphs = get_safe(data,"message","auxiliary_graphs")
        removed_ids=[]
        removed_nodes=[]

        #The set of ids of nodes that need to be removed is the intersection of the Nodes keys and the blocklist
        if nodes is not None:
            nodes_to_remove= list(set(blocklist) & set(nodes.keys()))
            #We remove those nodes first from the knowledge graph
            for node in nodes_to_remove:
                removed_nodes.append(nodes[node])
                del nodes[node]

            #Then we find any edges that have them as a subject or object and remove those
            edges_to_remove=[]
            for edge_id, edge in edges.items():
                if edge['subject'] in nodes_to_remove or edge['object'] in nodes_to_remove:
                    edges_to_remove.append(edge_id)
            for edge_id in edges_to_remove:
                del edges[edge_id]

            if aux_graphs is not None:
                aux_graphs_to_remove=[]
                for aux_id, aux_graph in aux_graphs.items():
                    edges = get_safe(aux_graph,"edges")
                    overlap = list(set(edges) & set(edges_to_remove))
                    if len(overlap)>0:
                        aux_graphs_to_remove.append(aux_id)
                for aux_id in aux_graphs_to_remove:
                    del aux_graphs[aux_id]
            #We do the same for results
            if results is not None:
                results_to_remove = []
                for result in results:
                    node_bindings = get_safe(result,"node_bindings")
                    if node_bindings is not None:
                        for k in node_bindings.keys():
                            nb=node_bindings[k]
                            for c in nb:
                                the_id = get_safe(c,"id")
                            if the_id in nodes_to_remove and result not in results_to_remove:
                                results_to_remove.append(result)

                    analyses=get_safe(result,"analyses")
                    if analyses is not None:
                        analyses_to_remove=[]
                        for analysis in analyses:
                            edge_bindings = get_safe(analysis,"edge_bindings")
                            if edge_bindings is not None:
                                for edge_id,bindings in edge_bindings.items():
                                    bindings_to_remove=[]
                                    for binding in bindings:
                                        if binding['id'] in edges_to_remove:
                                            if(len(bindings)>1):
                                                bindings_to_remove.append(binding)
                                            else:
                                                analyses_to_remove.append(analysis)
                                    for br in bindings_to_remove:
                                        bindings.remove(br)

                            support_graphs=get_safe(analysis,"support_graphs")
                            support_graphs_to_remove=[]
                            if support_graphs is not None and len(support_graphs)>0:
                                for sg in support_graphs:
                                    if sg in edges_to_remove:
                                        support_graphs_to_remove.append(sg)
                                for sg in support_graphs_to_remove:
                                    support_graphs.remove(sg)
                        for analysis in analyses_to_remove:
                            analyses.remove(analysis)
                        if len(analyses)<1 and result not in results_to_remove:
                            #if removing the bad analyses leaves us with a result that would have none, we remove the result
                            results_to_remove.append(result)
                for result in results_to_remove:
                    results.remove(result)

        list_of_names = []
        for node in removed_nodes:
            if "name" in node.keys():
                list_of_names.append(node["name"])

        logging.info('Removing results containing the following %s from PK: %s' % (str(nodes_to_remove), str(mesg.id)))
        log_tuple =[
            'Removed the following bad nodes: '+ str(list_of_names),
            datetime.now().strftime('%H:%M:%S'),
            "DEBUG"
        ]
        add_log_entry(data,log_tuple)
        #mesg.status='D'
        #mesg.code=200
        mesg.save_compressed_dict(data)
        #mesg.data=data
        mesg.save()

        return (str(mesg.id),removed_nodes,results_to_remove)
    except Exception as e:
        logging.error("Problem with removing results from block list ")
        logging.error(type(e).__name__)
        logging.info(e.args)
        logging.info(e, exc_info=True)
        logging.info('error message %s' % str(e))
        raise e


def scrub_null_attributes(data):
    nodes = get_safe(data,"message","knowledge_graph","nodes")
    edges = get_safe(data,"message","knowledge_graph","edges")
    if nodes is not None:
        for nodeId,nodeStuff in nodes.items():
            nodeAttributes = get_safe(nodeStuff,"attributes")
            if nodeAttributes is not None:
                while None in nodeAttributes:
                    nodeAttributes.remove(None)

    if edges is not None:
        bad_sources = []
        for edgeId, edgeStuff in edges.items():
            edgeAttributes =get_safe(edgeStuff,"attributes")
            if edgeAttributes is not None:
                while None in edgeAttributes:
                    edgeAttributes.remove(None)

            edgeSources=get_safe(edgeStuff, "sources")
            sources_to_remove = {}
            for edge_source in edgeSources:
                if 'resource_id' not in edge_source.keys() or edge_source["resource_id"] is None:
                    #logging.info('found Null in resource_id : %s' % (edge_source))
                    if edgeId not in sources_to_remove.keys():
                        sources_to_remove[edgeId]=[edge_source]
                    else:
                        sources_to_remove[edgeId].append(edge_source)

                if 'upstream_resource_ids' not in edge_source.keys() or ('upstream_resource_ids' in edge_source.keys() and edge_source["upstream_resource_ids"] is None):
                    #logging.info('found Null in upstream_resource_ids : %s' % (edge_source))
                    edge_source["upstream_resource_ids"]=[]
                if 'upstream_resource_ids' in edge_source.keys() and isinstance(edge_source['upstream_resource_ids'], list):
                    while None in edge_source["upstream_resource_ids"]:
                        edge_source["upstream_resource_ids"].remove(None)


            if len(sources_to_remove)>0:
                bad_sources.append(sources_to_remove)
            for key, sources in sources_to_remove.items():
                for source in sources:
                    edgeSources.remove(source)
        log_tuple =[
            "Removed the following bad sources: "+ str(bad_sources),
            datetime.now().strftime('%H:%M:%S'),
            "DEBUG"
        ]
        #add_log_entry(data,log_tuple)


def appraise(mesg,data, agent_name,retry_counter=0):
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    json_data = json.dumps(data)
    logging.info('sending data for agent: %s to APPRAISER URL: %s' % (agent_name, APPRAISER_URL))
    try:
        with requests.post(APPRAISER_URL,data=json_data,headers=headers, stream=True) as r:
            logging.debug("Appraiser being called at: "+APPRAISER_URL)
            logging.info('the response for agent %s to appraiser code is: %s' % (agent_name, r.status_code))
            if r.status_code==200:
                rj = r.json()
                #for now, just update the whole message, but we could be more precise/efficient
                logging.debug("Updating message with appraiser data for agent %s and pk %s " % (agent_name, str(mesg.id)))
                data['message']['results']=rj['message']['results']
                logging.debug("Updating message with appraiser data complete for "+str(mesg.id))
            else:
                retry_counter +=1
                logging.debug("Received Error state from appraiser for agent %s and pk %s  Code %s Attempt %s" % (agent_name,str(mesg.id),str(r.status_code),str(retry_counter)))
                logging.debug("JSON fields "+str(json_data)[:100])
                if retry_counter<3:
                    appraise(mesg,data, agent_name,retry_counter)
                else:
                    logging.error("3 consecutive Errors from appraise for agent %s and pk %s " % (agent_name,str(mesg.id)))
                    raise Exception
    except Exception as e:

        logging.error("Problem with appraiser for agent %s and pk %s " % (agent_name,str(mesg.id)))
        logging.error(type(e).__name__)
        logging.error(e.args)
        logging.error("Adding default ordering_components for agent %s and pk %s " % (agent_name,str(mesg.id)))
        raise e
        

def annotate_nodes(mesg,data,agent_name):
    #TODO pull this URL from SmartAPI
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    nodes = get_safe(data,"message","knowledge_graph","nodes")
    if nodes is not None:
        nodes_message = {
            "message":
                {
                    "knowledge_graph":{
                        "nodes":nodes
                    }
                }
        }
        #we have to scrub input for invalid CURIEs or we'll get a 500 back from the annotator
        curie_pattern = re.compile("[\w\.]+:[\w\.]+")
        invalid_nodes={}

        for key in nodes_message['message']['knowledge_graph']['nodes'].keys():
            if not curie_pattern.match(str(key)):
                invalid_nodes[key]=nodes_message['message']['knowledge_graph']['nodes'][key]
        if len(invalid_nodes)!=0:
            for key in invalid_nodes.keys():
                del nodes_message['message']['knowledge_graph']['nodes'][key]


        json_data = json.dumps(nodes_message)
        try:
            logging.info('posting data to the annotator URL %s' % ANNOTATOR_URL)
            # with open(str(mesg.pk)+'_'+agent_name+"_KG_nodes_annotator.json", "w") as outfile:
            #     outfile.write(json_data)
            r = requests.post(ANNOTATOR_URL,data=json_data,headers=headers)
            r.raise_for_status()
            rj=r.json()
            logging.info('the response status for agent %s node annotator is: %s' % (agent_name,r.status_code))
            if r.status_code==200:
                for key, value in rj.items():
                    if 'attributes' in value.keys() and value['attributes'] is not None:
                        for attribute in value['attributes']:
                            if attribute is not None:
                                add_attribute(data['message']['knowledge_graph']['nodes'][key],attribute)
                            
                    #Not sure about adding back clearly borked nodes, but it is in keeping with policy of non-destructiveness
                if len(invalid_nodes)>0:
                    data['message']['knowledge_graph']['nodes'].update(invalid_nodes)
            else:
                post_processing_error(mesg,data,"Error in annotation of nodes")
        except Exception as e:
            logging.info('node annotation internal error msg is for agent %s with pk: %s is  %s' % (agent_name,str(mesg.pk),str(e)))
            logging.exception("error in node annotation internal function")

            raise e
        #else:
         #   with open(str(mesg.actor)+".json", "w") as outfile:
          #      outfile.write(json_data)
           # post_processing_error(mesg,data,"Error in annotation of nodes")


def normalize_scores(mesg,data,key, agent_name):
    res=get_safe(data,"message","results")
    if res is not None:
        if len(res)>0:
            try:
                logging.info('going to normalize scores for agent: %s and pk: %s' % (agent_name, key))
                data["message"]["results"] = normalizeScores(res)
            except Exception as e:
                logging.error('Failed to normalize scores for agent: %s and pk: %s' % (agent_name, key))
                logging.exception('failed to normalize scores for agent: %s and pk: %s' %(agent_name, key))
                raise e


def normalize_nodes(data,agent_name,key):
    res = get_safe(data,"message","results")
    kg = get_safe(data,"message", "knowledge_graph")
    if kg is not None:
        if res is not None:
            logging.info('going to normalize ids for agent: %s and pk: %s' % (agent_name, key))
            try:
                kg, res = canonizeMessageTest(kg, res)
            except Exception as e:
                logging.error('Failed to normalize ids for agent: %s and pk: %s' % (agent_name, key))
                logging.exception('failed to normalize ids for agent: %s and pk: %s' % (agent_name, key))
                raise e
        else:
            logging.debug('the %s has not returned any result back for pk: %s' % (agent_name, key))
    else:
        logging.debug('the %s has not returned any knowledge_graphs back for pk: %s' % (agent_name, key))

def decorate_edges_with_infores(data,inforesid):
    edges = get_safe(data,"message","knowledge_graph","edges")
    if inforesid is None:
        inforesid="infores:unknown"
    self_source= {
        "resource_id": inforesid,
        "resource_role": "primary_knowledge_source",
        "source_record_urls": None,
        "upstream_resource_ids": []
    }
    if edges is not None:
        for key, edge in edges.items():
            has_self=False
            if 'sources' not in edge.keys() or edge['sources'] is None or len(edge['sources'])==0:
                edge['sources']=[self_source]
            else:
                bad_sources=[]
                for source in edge['sources']:
                    if source['resource_id']==inforesid:
                        has_self=True

                    if source['resource_role']=="primary_knowledge_source":
                        has_primary=True
                if not has_self:
                    #if we already have a primary knowledge source but not our self, we add ourself as an aggregator
                    if has_primary:
                        self_source['resource_role']="aggregator_knowledge_source"
                    else:
                        self_source["resource_role"]="primary_knowledge_source"
                    #then we add it, be it primary or aggregator
                    edge['sources'].append(self_source)


def post_processing_error(mesg,data,text):
    mesg.status = 'E'
    mesg.code = 206
    log_tuple=[text,
               (mesg.updated_at).strftime('%H:%M:%S'),
               "WARNING"]
    logging.info(f'the log_tuple is %s'% log_tuple)
    add_log_entry(data,log_tuple)

def add_log_entry(data, log_tuple):
    #log_tuple should be a tuple of:
    #message
    #timestamp
    #level
    log_entry={
        "message":log_tuple[0],
        "timestamp":log_tuple[1],
        "level":log_tuple[2]
    }
    if 'logs' in data.keys():
        data['logs'].append(log_entry)
    else:
        data['logs'] = [log_entry]

def add_attribute(node_or_edge, attribute_json):
    template_attribute= {
        "value": None,
        "value_url": None,
        "attributes": None,
        "description": None,
        "value_type_id": None,
        "attribute_source": None,
        "attribute_type_id": None,
        "original_attribute_name": None
    }
    for key in attribute_json.keys():
        if key is not None and key in template_attribute.keys():
            template_attribute[key]=attribute_json[key]
    if 'attributes' in node_or_edge.keys():
        node_or_edge['attributes'].append(template_attribute)
    else:
        node_or_edge['attributes']=[template_attribute]

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
        "conflate":True,
        "drug_chemical_conflate":True
    }
    logging.info('the normalizer_URL is %s' % NORMALIZER_URL)
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
        changes ={}
        canonical = canonize(ids)
        for canon in canonical:
            if canon in nodes:
                new_name=get_safe(canonical[canon],'id','label')
                if new_name is not None and ('name' not in nodes[canon] or ('name' in nodes[canon] and nodes[canon]['name']!= new_name)):
                        nodes[canon]['name'] = new_name
                if canonical[canon] is not None and canon != canonical[canon]["id"]["identifier"]:
                    changes[canon]=canonical[canon]
                    new_id = changes[canon]['id']['identifier']
                    nodes[new_id]=nodes.pop(canon)

                    original_node={
                        "attribute_type_id": "biolink:xref",
                        "original_attribute_name": "original_id",
                        "value": [canon],
                        "value_type_id": "metatype:NodeIdentifier",
                        "attribute_source": None,
                        "value_url": None,
                        "description": None,
                    }
                    if 'equivalent_identifiers' in canonical[canon].keys():
                        same_as_attribute = {
                            'attribute_type_id': 'biolink:same_as',
                            'original_attribute_name': 'equivalent_identifiers',
                            'value': [
                                node['identifier'] for node in canonical[canon]['equivalent_identifiers']
                            ],
                            "value_type_id": "metatype:NodeIdentifier",
                            "attribute_source": None,
                            "value_url": None,
                            "description": None,
                        }

                    if 'attributes' in nodes[new_id] and isinstance(nodes[new_id]['attributes'], list):
                        attributes = nodes[new_id]['attributes']
                        if any('original_attribute_name' in x.keys() and x['original_attribute_name'] == 'equivalent_identifiers' for x in attributes):
                            attributes.append(original_node)
                        else:
                            attributes.extend((original_node, same_as_attribute))
                    elif 'attributes' not in nodes[new_id]:
                        #logging.debug("attribute field doesnt exist in the current node")
                        nodes[new_id]['attributes'] = [original_node, same_as_attribute]
                    elif nodes[new_id]['attributes'] is None:
                        #logging.debug("attribute field is None in the current node")
                        nodes[new_id]['attributes'] = [original_node, same_as_attribute]
                    else:
                        logging.debug("attribute not of type list")
                        if 'equivalent_identifiers' in nodes[new_id]['attributes']['original_attribute_name']:
                            nodes[new_id]['attributes'] = [original_node]
                        else:
                            nodes[new_id]['attributes'] = [original_node, same_as_attribute]

                    if 'categories' not in nodes[new_id]:
                        nodes[new_id]['categories'] = canonical[canon]['type']
                    # categories = nodes[new_id]['categories']
                    # if 'type' in canonical[canon].keys():
                    #     if type(canonical[canon]['type']) is list and type(categories) is list:
                    #         canon_category = canonical[canon]['type']
                    #         categories.extend(list(set(canon_category)-set(categories)))

        #by this time get a list of ids in nodes and look for duplicates
        normalized_nodes = list(nodes.keys())
        if len(normalized_nodes) != len(set(normalized_nodes)):
            logging.debug('found duplicates in normalized nodes set')

        bindings=[res['node_bindings'] for res in results]
        for binding in bindings:
            for key in binding.keys():
                id_list = binding[key]
                for id_dict in id_list:
                    if id_dict['id'] in changes:
                        id_dict['id']=changes[id_dict['id']]['id']['identifier']

        for change in changes:
            for edge_key,edge_value in edges.items():
                for key,value in edge_value.items():
                    if change == value:
                        new_id = changes[change]['id']['identifier']
                        edges[edge_key][key] = new_id

        #create a frozenset of subj/obj/predicate on each edge and look for duplicates
        # normalized_edges=[]
        # for edge_key,edge_value in edges.items():
        #     tuple = (edge_value['subject'], edge_value['object'], edge_value['predicate'])
        #     normalized_edges.append(tuple)
        # c = Counter(normalized_edges) - Counter(set(normalized_edges))
        # res = {}
        # for i, elem in enumerate(normalized_edges):
        #     if elem in c:
        #         item = res.get(elem)
        #         if item:
        #             item.append(i)
        #         else:
        #             res[elem] = [i]
        # print(res)
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
    scoreList = []
    if results is not None and len(results)>0:
        for res in results:
            if 'analyses' in res.keys() and res['analyses'] != [] and res['analyses'] is not None:
                if len(res['analyses']) > 1:
                    temp_score = []
                    for analysis in res['analyses']:
                        if 'score' in analysis.keys():
                            temp_score.append(analysis['score'])
                    score = statistics.mean(temp_score)

                elif len(res['analyses']) == 1:
                    if 'score' in res['analyses'][0]:
                        score = res['analyses'][0]['score']
                    else:
                        logging.debug('Result doesnt have score field')
                        score = None


                if score is not None:
                    scoreList.append(score)
            else:
                logging.error("Results dont have the required fields")
                return stat

        try:
            if len(scoreList) <= 1:
                return stat
            stat['median'] = statistics.median(scoreList)
            stat['mean'] = statistics.mean(scoreList)
            stat['stdev'] = statistics.stdev(scoreList)
            stat['minimum'] = min(scoreList)
            stat['maximum'] = max(scoreList)
        except Exception as e:
            logging.error("Error in calculating statistics")
            logging.error(e.__traceback__)
            return stat
    return stat

def normalizeScores(results):

    scoreList = []
    if results is not None and len(results)>0:
        for res in results:
            if 'analyses' in res.keys() and res['analyses'] != [] and res['analyses'] is not None:
                if len(res['analyses']) > 1:
                    temp_score = []
                    for analysis in res['analyses']:
                        if 'score' in analysis.keys():
                            if analysis['score'] is not None:
                                temp_score.append(analysis['score'])
                            else:
                                logging.error("Analyses score field is null, setting it to zero")
                                analysis['score']=0
                                temp_score.append(analysis['score'])

                    score = statistics.mean(temp_score)

                elif len(res['analyses']) == 1:
                    if 'score' in res['analyses'][0]:
                        if res['analyses'][0]['score'] is not None:
                            score = res['analyses'][0]['score']
                        else:
                            score = 0
                    else:
                        logging.debug('Result doesnt have score field')
                        score = None


                if score is not None:
                    scoreList.append(score)
            else:
                logging.error("Results dont have the required fields")
                return results

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
            messageList.append(get_object_or_404(Message.objects.filter(pk=childPk)))
    return messageList

def createMessage(actor,parent_pk):

    message = Message.create(code=202, status='Running',
                             actor=actor, ref=get_object_or_404(Message.objects.filter(pk=parent_pk)))
    message.save()
    return message


@app.task(name="merge")
def merge(pk,merged_pk):
    messageList= getChildrenFromParent(pk)
    mergedComplete = get_object_or_404(Message.objects.filter(pk=merged_pk))

    newList =[]
    for message in messageList:
        mesg=get_safe(message.to_dict(),"fields","data","message")
        if mesg is not None:
            t_mesg=TranslatorMessage(message.to_dict()["fields"]["data"]["message"])
        else:
            continue
        if t_mesg.getKnowledgeGraph() is not None:
            newList.append(t_mesg)

    merged = mergeMessages(newList)
    mergedComplete.data=merged.to_dict()
    mergedComplete.code = 200
    mergedComplete.status = 'D'
    mergedComplete.save()

@app.task(name="merge_received")
def merge_received(parent,message_to_merge, agent_name, counter=0):
    current_merged_pk=parent.merged_version_id
    logging.info("Beginning merge for agent %s with current_pk: %s" %(agent_name,str(current_merged_pk)))
    #to_merge_message= Message.objects.get(pk=pk_to_merge)
    #to_merge_message_dict=get_safe(to_merge_message.to_dict(),"fields","data","message")
    t_to_merge_message=TranslatorMessage(message_to_merge)
    new_merged_message = createMessage(get_ars_actor(),str(parent.pk))
    logging.info("the merged_pk for agent %s is %s" % (agent_name, str(new_merged_message.pk)))
    new_merged_message.save()
    # #Since we've started a merge, we lock the parent PK for the duration (this is a soft lock)
    # parent.merge_semaphore=True
    # parent.save()
    try:
        #If at least one merger has already occurred, we merge the newcomer into that
        if current_merged_pk is not None :
            current_merged_message=get_object_or_404(Message.objects.filter(pk=current_merged_pk))
            #current_merged_decomp_message = current_merged_message.decompress_json()
            current_message_dict = get_safe(current_merged_message.to_dict(),"fields","data","message")
            t_current_merged_message=TranslatorMessage(current_message_dict)
            if current_message_dict is not None:
                merged=mergeMessages([
                    t_current_merged_message,
                    t_to_merge_message,
                ],
                str(new_merged_message.pk))
            else:
                logging.error(f'current message dictionary returns none')
            print()
        #If not, we make the newcomer the current "merged" Message
        else:
            logging.info("first merge done on agent: %s" % agent_name)
            merged = t_to_merge_message


        merged_dict = merged.to_dict()
        logging.info('the keys for merged_dict are %s' % merged_dict['message'].keys())
        new_merged_message.save_compressed_dict(merged_dict)
        # new_merged_message.data = merged_dict
        new_merged_message.status='R'
        new_merged_message.code=202
        new_merged_message.save()

        #Now that we're done, we unlock update the merged_version on the parent, unlock it, and save
        parent.merged_version=new_merged_message
        parent.merge_semaphore=False
        #Need to do this because JSONFields in Django can't have a default (of [] in this case).
        #So, it starts as None/null
        new_merged_message_id_string=str(new_merged_message.id)
        pk_infores_merge = (new_merged_message_id_string, agent_name)
        if parent.merged_versions_list is None:
            parent.merged_versions_list=[pk_infores_merge]
        else:
            parent.merged_versions_list.append(pk_infores_merge)
        parent.save(update_fields=['merge_semaphore','merged_versions_list', 'merged_version'])
        logging.info("returning new_merged_message to be post processed with pk: %s" % str(new_merged_message.pk))
        return new_merged_message
    except Exception as e:
        logging.exception("problem with merging for %s :" % agent_name)
        #If anything goes wrong, we at least need to unlock the semaphore
        #TODO make some actual proper Exception handling here.
        parent.merge_semaphore=False
        parent.save()
        logging.info("return  empty dict for merged results")
        return {}



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

