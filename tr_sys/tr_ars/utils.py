import copy
import json
import traceback
import requests
import urllib
import sys
NORMALIZER_URL='https://nodenormalization-sri.renci.org/1.2/get_normalized_nodes?'
class QueryGraph():
    pass
    def __init__(self,qg):
        if qg==None:
            return None
        self.rawGraph = qg
        self.__nodes =  qg['nodes']
        self.__edges = qg['edges']
    def getEdges(self):
        return self.__edges
    def getNodes(self):
        return self.__edges
    def getAllCuries(self):
        nodes = self.getNodes()
        curies =[]
        for node in nodes:
            if("curie") in node:
                curies.append(node['curie'])
        return curies

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
            if  isinstance(node['id'],list):
                print()
            ids.append(node['id'])
        return ids
    def getNodeById(self,id):
        nodes = self.getNodes()
        for node in nodes:
            if node['id']==id:
                return node
        return None
    def getEdgeById(self,id):
        edges = self.getEdges()
        for edge in edges:
            if edge['id']==id:
                return edge
        return None

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
                logger.error("Unexpected error 3: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
                print()
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
            for binding in eb:
                id = binding['kg_id']
                edge = kg.getEdgeById(id)
                source = edge['source_id']
                type = edge['type']
                target = edge['target_id']
                tuple = (source,type,target)
                tuples.add(tuple)
            resultTuples.add(frozenset(tuples))
        return resultTuples

    def setQueryGraph(self,qg):
        self.__qg=qg
    def setKnowledgeGraph(self,kg):
        self.__kg=kg
    def setResults(self,results):
        self.__results=results
    def setSharedResults(self,sharedResults):
        self.__sharedResults=sharedResults


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
    print()
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



def mergeMessages(originalQuery,messageList):
    messageListCopy = copy.deepcopy(messageList)
    message = messageListCopy.pop()
    message.setQueryGraph(originalQuery)
    merged = mergeMessagesRecursive(message,messageListCopy)
    print()
    return merged

def mergeMessagesRecursive(mergedMessage,messageList):
    if len(messageList)==0:
        return mergedMessage
    else:
        currentMessage = messageList.pop()
        #merge Knowledge Graphs
        mergedKnowledgeGraph = mergeKnowledgeGraphs(currentMessage.getKnowledgeGraph(),mergedMessage.getKnowledgeGraph())

        #merge Results
        currentResultTuples = currentMessage.getResultTuples()
        mergedResultTuples = mergedMessage.getResultTuples()
        sharedResultTuples=set()
        for cts in currentResultTuples:
            if cts in mergedResultTuples:
                sharedResultTuples.add(cts)
        if len(sharedResultTuples)>0:
            if mergedMessage.getSharedResults() is not None:
                currentSharedMap = mergedMessage.getSharedResults()
                intersectingResults = set(currentSharedMap.keys()).intersection(sharedResultTuples)
                for key in currentSharedMap.keys():
                    if key in intersectingResults:
                        currentSharedMap[key]=currentSharedMap[key]+1
                    else:
                        currentSharedMap[key]=2
                mergedMessage.setSharedResults(currentSharedMap)
            else:
                resultMap={k:2 for k in sharedResultTuples}
                mergedMessage.setSharedResults(resultMap)
        mergedResults=mergeResults(currentMessage.getResults(),mergedMessage.getResults())
        mergedMessage.setResults(mergedResults)
        mergedMessage.setKnowledgeGraph(mergedKnowledgeGraph)
        return mergeMessagesRecursive(mergedMessage,messageList)


def mergeResults(r1, r2):
    return Results(r1.getRaw()+r2.getRaw())
def mergeKnowledgeGraphs(kg1, kg2):
    mergedNodes =[]
    firstIds = set(kg1.getAllIds())
    try:
        idTest = kg2.getAllIds()
        secondIds = set(idTest)
    except Exception as e:
        logger.error("Unexpected error 4: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
        print()
    intersection = firstIds.intersection(secondIds)
    firstOnly = firstIds.difference(secondIds)
    secondOnly = secondIds.difference(firstIds)
    for id in firstOnly:
        mergedNodes.append(kg1.getNodeById(id))
    for id in secondOnly:
        mergedNodes.append(kg2.getNodeById(id))
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
            mergedNodes.append(mergedNode)

    #Since edges don't have the same guarantee of identifiers matching as nodes, we'll just combine them naively and
    #eat the redundancy if we have two functionally identical edges for now
    mergedEdges=kg1.getEdges()+kg2.getEdges()
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
def canonize(curie):
    url_curie = urllib.parse.quote_plus(curie)
    r = requests.get(NORMALIZER_URL+"curie="+url_curie)
    response = r.json()
    canonical_curie = get_safe(response,curie,"id","identifier")
    if canonical_curie is not None:
        return canonical_curie
    else:
        return curie

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

def findSharedResults(sharedResults,messageList):
    canonicalResults=[]
    for message in messageList:
        results = canonizeResults(message.getResults())
        canonicalResults.append(results)