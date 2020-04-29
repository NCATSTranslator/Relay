from flask import Flask, request, url_for, jsonify, abort
import requests, sys, threading, time

ARS_API = 'http://localhost:8000/ars/api'

def setup_app():
    DEFAULT_ACTOR = {
        'channel': 'general',
        'agent': {
            'name': 'ara-simple-agent',
            'uri': 'http://localhost:5000'
        },
        'path': '/simple' # relative to agent's uri
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
    return 'A simple ARA that does nothing!'

@app.route('/simple', methods=['POST'])
def simple():
    data = request.get_json()
    if 'model' not in data or data['model'] != 'tr_ars.message':
        return abort(400)
    app.logger.debug('%s: received message...%s' % (request.url, data['pk']))
    mesg = data['fields']
    if 'ref' not in mesg or mesg['ref'] != None:
        # this is not a head message, so we're not interested
        return abort(400)
    
    return jsonify(message="This is an acknowledge that I have nothing to contribute to this query!"), 200, {'tr_ars.message.status': 'D'} # set the status of the message

if __name__ == '__main__':
    app.run()
    
