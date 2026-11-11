import requests
import os
import json
import pytest
from pathlib import Path
import gzip
import zstandard as zstd
from tests.helper.generate import get_curie
from biothings_annotator import annotator

# Everything here calls a live service; excluded by default, run with: pytest -m integration
pytestmark = pytest.mark.integration

hostname=os.getenv('TARGET_HOST') if os.getenv("TARGET_HOST") is not None else 'ars.ci.transltr.io'
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


@pytest.mark.asyncio
async def test_biothings_annotator():

    curies=get_curie()
    atr = annotator.Annotator()
    result = await atr.annotate_curie_list(curies)

    assert result is not None
    assert isinstance(result, dict)


