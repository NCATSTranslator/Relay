from contextlib import closing
import requests
import json
import sys
import os
import subprocess
import time

dbfile = "tr_sys/db.sqlite3"
python = sys.executable #python or python3
server = "http://localhost:8000/ars"

def addUnsecret():
    syscall = ["curl", "-d", "@tr_sys/tr_ara_unsecret/unsecretAgent.json", server+"/api/agents"]
    fp = subprocess.run(syscall, capture_output=True)
    agent = json.loads(fp.stdout)
    assert agent["model"] == "tr_ars.agent"
    syscall = ["curl", "-d", "@tr_sys/tr_ara_unsecret/unsecretActor.json", server+"/api/actors"]
    fp = subprocess.run(syscall, capture_output=True)
    actor = json.loads(fp.stdout)
    assert actor["model"] == "tr_ars.actor"
    return actor["pk"]

def execUnsecret(unsecret):
    syscall = ["curl", "-d", "@tr_sys/tr_ara_unsecret/unsecretStatusQuery.json", server+"/api/submit"]
    fp = subprocess.run(syscall, capture_output=True)
    message = json.loads(fp.stdout)
    assert message["model"] == "tr_ars.message"
    time.sleep(5)
    response = requests.get(server+"/api/messages/"+message["pk"]+"?trace=y")
    chain = response.json()
    print(chain)
    for child in chain["children"]:
        if child["actor"]["pk"] == unsecret:
            response = requests.get(server+"/api/messages/"+child["message"])
            print(response.json())
            answer = response.json()
            assert len(answer["fields"]["data"]["results"]) > 1
            return
    raise

def validateQuery():
    url ='http://transltr.io:7071/validate_querygraph'
    testJson = json.loads(open('./data/travis.json').read())
    with closing(requests.post(url, json=testJson, stream=False)) as response:
        status_code = response.status_code

        assert status_code == 200

def runTests():
    unsecret = addUnsecret()
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
        if sys.argv[1] == 'prep' or sys.argv[1] == 'test':
            if os.path.exists(dbfile):
                os.remove(dbfile)
            subprocess.run([python, "tr_sys/manage.py", "makemigrations", "tr_ars"])
            subprocess.run([python, "tr_sys/manage.py", "migrate"])

        if sys.argv[1] == 'prep':
            sys.exit()

        # bring up server
        serverfp = None
        serverargs = [python, "tr_sys/manage.py", "runserver", "--noreload"]
        if sys.argv[1] == 'test':
            serverfp = subprocess.Popen(serverargs, stdout=sys.stdout, stderr=sys.stderr)
            time.sleep(5)
        if sys.argv[1] == 'prod':
            serverfp = subprocess.run(serverargs, stdout=sys.stdout, stderr=sys.stderr)

        # run tests
        if sys.argv[1] == 'test' or sys.argv[1] == 'debug':
            runTests()
            if serverfp != None:
                serverfp.terminate()
                time.sleep(5)
            sys.exit()

    sys.stderr.write('''Usage: python server.py [mode] [opts]
        ... where [mode] is one of:
        prep  --- delete existing db file and prep a new db
        debug --- for running tests on a running localhost:8000 server with existing db
        test  --- deletes existing db and starts a new server on localhost:8000 for testing
        prod  --- starts a new server only\n''')
    sys.exit(1)
