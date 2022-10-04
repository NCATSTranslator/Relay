import requests
import os

hostname=os.getenv('TARGET_HOST')
def test_agent_endopoint():
    response = requests.get("https://"+hostname+"/ars/api/agents")
    response_body = response.json()
    agent_names=[]
    for agent in response_body:
        agent_names.append(agent['fields']['name'])
    print(agent_names)
    assert "ara-aragorn" in agent_names


def test_actor_endpoint():
    response = requests.get("https://"+hostname+"/ars/api/actors")
    response_body = response.json()
    acotr_agent_names=[]
    for actor in response_body:
        acotr_agent_names.append(actor['fields']['agent'])
    assert "ara-aragorn" in acotr_agent_names



