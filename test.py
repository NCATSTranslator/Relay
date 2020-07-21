from contextlib import closing
import requests
import json
url ='http://transltr.io:7071/validate_querygraph'
testJson = json.loads(open('./data/travis.json').read())
with closing(requests.post(url, json=testJson, stream=False)) as response:
    
    status_code = response.status_code
    print(status_code)
    assert status_code == 200

                              
