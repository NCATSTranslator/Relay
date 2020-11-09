from contextlib import closing
import requests
import json
import sys
import os
import subprocess
from subprocess import PIPE
import time

dbfile = "tr_sys/db.sqlite3"
python = sys.executable #python or python3
server = "http://localhost:8000"

def getUnsecret():
    # syscall = ["curl", "-d", "@tr_sys/tr_ara_unsecret/unsecretAgent.json", server+"/api/agents"]
    # fp = subprocess.run(syscall, stdout=PIPE)
    # agent = json.loads(fp.stdout)
    # assert agent["model"] == "tr_ars.agent"
    # syscall = ["curl", "-d", "@tr_sys/tr_ara_unsecret/unsecretActor.json", server+"/api/actors"]
    # fp = subprocess.run(syscall, stdout=PIPE)
    # actor = json.loads(fp.stdout)
    # assert actor["model"] == "tr_ars.actor"
    response = requests.get(server+"/ars/api/actors")
    actors = response.json()
    actorpk = 0
    for actor in actors:
        if 'fields' in actor:
            if actor['fields']['name'] == "ara-unsecret-runquery":
                actorpk = actor['pk']
    if actorpk == 0:
        sys.stderr.write("Unsecret actor not found!\n")
        assert actorpk > 0
    return actorpk

def execUnsecret(unsecret):
    syscall = ["curl", "-d", "@tr_sys/tr_ara_unsecret/unsecretStatusQuery.json", server+"/ars/api/submit"]
    fp = subprocess.run(syscall, stdout=PIPE)
    message = json.loads(fp.stdout)
    assert message["model"] == "tr_ars.message"
    for i in range(5):
        time.sleep(i*i*5)
        response = requests.get(server+"/ars/api/messages/"+message["pk"]+"?trace=y")
        chain = response.json()
        #print(chain)
        print ("i ="+str(i))
        for child in chain["children"]:
            if child["actor"]["pk"] == unsecret:
                response = requests.get(server+"/ars/api/messages/"+child["message"])
                #print(str(response.json())[:500])
                print("found unsecret")
                answer = response.json()
                if answer["fields"]["status"] != "Running":
                    print("retrieved message: "+response.url)
                    assert len(answer["fields"]["data"]["results"]) > 1
                    return
    sys.stderr.write("Could not find Unsecret message response!\n")
    assert unsecret < 0
    return message

def validateQuery():
    url ='http://transltr.io:7071/validate_querygraph'
    testJson = json.loads(open('./data/travis.json').read())
    with closing(requests.post(url, json=testJson, stream=False)) as response:
        status_code = response.status_code

        assert status_code == 200

def runTests():
    unsecret = getUnsecret()
    execUnsecret(unsecret)

if __name__ == "__main__":

    if len(sys.argv) > 1 and '--help' not in sys.argv and '-h' not in sys.argv:
        if "--dbfile" in sys.argv:
            dbfile = sys.argv[sys.argv.index("--dbfile")+1]
        if "--python" in sys.argv:
            python = sys.argv[sys.argv.index("--python")+1]
        if "--server" in sys.argv:
            server = sys.argv[sys.argv.index("--server")+1]
        try:
            subprocess.run([python, "--version"])
        except AttributeError as err:
            sys.stderr.write("Requires Python 3 ... maybe you are running Python 2?\n")
            print("OS error: {0}".format(err))
            sys.exit(1)

        # setup db
        if sys.argv[1] == 'prep' or sys.argv[1] == 'debug':
            if os.path.exists(dbfile):
                os.remove(dbfile)
            subprocess.run([python, "tr_sys/manage.py", "makemigrations", "tr_ars"])
            subprocess.run([python, "tr_sys/manage.py", "migrate"])

        if sys.argv[1] == 'prep':
            sys.exit()

        # bring up server
        serverfp = None
        serverargs = [python, "tr_sys/manage.py", "runserver", "--noreload"]
        if sys.argv[1] == 'debug':
            serverfp = subprocess.Popen(serverargs, stdout=PIPE, stderr=PIPE)
            time.sleep(5)
        if sys.argv[1] == 'prod':
            serverfp = subprocess.run(serverargs, stdout=PIPE, stderr=PIPE)

        # run tests
        if sys.argv[1] == 'debug' or sys.argv[1] == 'test':
            runTests()
            if serverfp != None:
                serverfp.terminate()
                time.sleep(5)
            sys.exit()

    sys.stderr.write('''Usage: python server.py [mode] [opts]
        ... where [mode] is one of:
        prep  --- delete existing db file and prep a new db
        test --- for running tests on a running localhost:8000 server with existing db
        debug  --- deletes existing db and starts a new server on localhost:8000 for testing
        prod  --- starts a new server only
        
        options:
        --server [uri]
            server uri to test, e.g. http://localhost:8000
        --dbfile [filename]
            if needed to overwrite backend during testing (debug)
        --python [path to exec]
            python3 executable

        \n''')
    sys.exit(1)
