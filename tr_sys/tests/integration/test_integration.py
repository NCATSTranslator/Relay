import requests
import os
import json
import pytest
from pathlib import Path
import gzip
import zstandard as zstd
from tests.helper.generate import get_curie
from biothings_annotator import annotator

hostname=os.getenv('TARGET_HOST') if os.getenv("TARGET_HOST") is not None else 'ars.ci.transltr.io'
NORMALIZER_URL=os.getenv("TR_NORMALIZER") if os.getenv("TR_NORMALIZER") is not None else "https://nodenormalization-sri.renci.org/1.5/get_normalized_nodes"
APPRAISER_URL=os.getenv("TR_APPRAISE") if os.getenv("TR_APPRAISE") is not None else "https://answerappraiser.ci.transltr.io/get_appraisal"

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


def test_normalizer_endpoint():
    curies = ['MESH:D014867', 'NCIT:C34373']
    j ={
        "curies":curies,
        "conflate":True,
        "drug_chemical_conflate":True
    }
    try:
        response = requests.post(NORMALIZER_URL, json.dumps(j))
        rj=response.json()
        assert response.status_code == 200
        #warning: the content of node norm response might change in future, keep an eye for it
        assert set(curies) == set(rj.keys()) #using set cause we dont wanne care about the order

    except requests.exceptions.RequestException as e:
        pytest.fail(f"Request failed: {e}")

@pytest.mark.asyncio
async def test_biothings_annotator():

    curies=get_curie()
    atr = annotator.Annotator()
    result = await atr.annotate_curie_list(curies)

    assert result is not None
    assert isinstance(result, dict)

def test_appraiser():

    file_path = Path(__file__).parent.parent / "helper/appraiser_data_input.zst"
    with open(file_path, "rb") as f:
        response = requests.post(
            APPRAISER_URL,
            data=f,
            headers = {'Accept-Encoding': 'zstd','Content-Encoding': 'zstd'},
            timeout=600
        )
        decompressor = zstd.ZstdDecompressor()
        rj = json.loads(decompressor.decompress(response.content).decode('utf-8'))

    assert response.status_code == 200
    assert isinstance(rj, dict)
    assert response.text != ""          # Raw string body
    assert response.content is not None # Raw byte content
