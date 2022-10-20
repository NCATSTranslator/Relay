import requests
import json
import os
import logging
import webbrowser
import time
import argparse
from collections import Counter

parser = argparse.ArgumentParser(description='Infores Result Count')
parser.add_argument('--pk', help='Main pk returned from sending json query')


def get_children_response(main_pk):
    
    done_response={}
    url=f"https://ars-prod.transltr.io/ars/api/messages/{main_pk}?trace=y"
    r = requests.get(url)
    parent_rj = r.json()
    for child in parent_rj['children']:
        if child['status'] == 'Done':
            done_response[child['actor']['inforesid']]= child['message'] 

    return done_response

def get_returned_result_edges(done_response):

    result_response={}
    infores_count_list=[]
    for infores, pk in done_response.items():
        edge_list=[]
        url=f"https://ars-prod.transltr.io/ars/api/messages/{pk}"
        r = requests.get(url)
        child_rj = r.json()
        if len(child_rj['fields']['data']['message']['results']) != 0:
            result_response[infores]=pk
            #edge_binding
            for result in child_rj['fields']['data']['message']['results']:
                for edge, values in result['edge_bindings'].items(): 
                    for value in values:
                        edge_list.append(value['id'])
            #remove duplicate edges
            unique_edge_id = set(edge_list)

            #counting infores appearance in each knowledge_graph
            kg_edge=child_rj['fields']['data']['message']['knowledge_graph']['edges']
            infores_count={}
            for edge in unique_edge_id:
                for key,values in kg_edge.items():
                    if edge == key:
                        for val in values['attributes']:
                            if 'attribute_source' in val:
                                if val['attribute_source'] is not None:
                                    infores = val['attribute_source'].split(':')[1]
                                    infores_count[infores] = infores_count.get(infores,0) + 1
                            else:
                                pass  

            infores_count_list.append(infores_count)                        
            
    return result_response, infores_count_list



def main():
    
    #logging.basicConfig(filename='myapp.log', level=logging.DEBUG)
    args = parser.parse_args()
    main_pk = getattr(args,"pk")
    
    done_response = get_children_response(main_pk)
    print("the following tools retunred Done status: {}".format(done_response))

    result_response, infores_count_list = get_returned_result_edges(done_response)
    print("the following tools retuned results: {}".format(result_response))

    final_infores_count=Counter()
    for infores in infores_count_list:
        final_infores_count.update(infores)
    
    print(dict(final_infores_count))
    

if __name__== '__main__':
    main()


