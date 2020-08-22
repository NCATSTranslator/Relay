from contextlib import closing
import requests
import json
import os
import time

time.sleep(20) # wait for server to come up

syscall = "curl -d @tr_sys/tr_ara_unsecret/unsecretAgent.json http://localhost:8000/ars/api/agents"
fp = os.popen(syscall)
print(fp.readlines())
fp.close()
syscall = "curl -d @tr_sys/tr_ara_unsecret/unsecretActor.json http://localhost:8000/ars/api/actors"
fp = os.popen(syscall)
print(fp.readlines())
fp.close()


url ='http://transltr.io:7071/validate_querygraph'
testJson = json.loads(open('./data/travis.json').read())
with closing(requests.post(url, json=testJson, stream=False)) as response:
    status_code = response.status_code

    assert status_code == 200

                              
