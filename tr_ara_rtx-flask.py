from flask import Flask, request, url_for, jsonify, abort
import requests, sys, threading, time, json
import traceback

ARS_API = 'http://localhost:8000/ars/api'
RTX_URL = 'https://arax.rtx.ai/api/rtx/v1/query'

def setup_app():
    DEFAULT_ACTOR = {
        'channel': 'general',
        'agent': {
            'name': 'ara-rtx-agent',
            'uri': 'http://localhost:5000'
        },
        'path': '/rtxquery' # relative to agent's uri
    }

    # wait for flask to finish intializing before it can accept
    # connections from the ars
    time.sleep(2) 
    r = requests.post(ARS_API+'/actors', json=DEFAULT_ACTOR)
    if r.status_code != 201 and r.status_code != 302:
        app.logger.error('Unable to intialize actor; %s return status %d'
                         % (r.url, r.status_code))
        sys.exit(1)
    
    print('initializing %s...%d\n%s' % (__name__, r.status_code, r.text))

app = Flask(__name__)
threading.Thread(target=setup_app).start()

@app.route('/', methods=['GET'])
def index():
    return 'A wrapper ARA for RTX!'

@app.route('/rtxquery', methods=['POST'])
def rtxquery():
    data = request.get_json()
    if 'model' not in data or data['model'] != 'tr_ars.message':
        return abort(400)
    app.logger.debug('%s: received message...%s' % (request.url, data['pk']))
    mesg = data['fields']
    if 'ref' not in mesg or mesg['ref'] != None:
        # this is not a head message, so we're not interested
        return abort(400)
    try:
        data = json.loads(mesg['data'])
        r = requests.post(RTX_URL, json=data, timeout=60)
        return (jsonify(r.text),
                r.status_code, # return status code
                {'tr_ars.message.status': 'D'}) # set the status of the message
    except Exception as e:
        app.logger.error("RTX failed: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
    
            
if __name__ == '__main__':
    app.run()
    
