ARS implementation
==================

### Prerequisites

Require python 3+, django 3.1+ and channels packages.

Test your python environment
```bash
python --version
```
> You might need to use `python3` and `pip3` commands on your system if Python is bound to 2.7


Install dependencies from the [requirements.txt](https://github.com/NCATSTranslator/Relay/blob/master/requirements.txt) in the root of the GitHub repository
```bash
pip install -r requirements.txt
```

### Setup

Create the django database

```bash
python tr_sys/manage.py makemigrations tr_ars
python tr_sys/manage.py migrate
python tr_sys/manage.py createsuperuser
```

Start RabbitMQ

```bash
docker run -d -p 5672:5672 rabbitmq
```

Start Celery task queuing

ensure that `USE_CELERY=True` in tr_sys/settings.py

```bash
cd tr_sys; celery -A tr_sys worker -l info
```

Bring up the server

```bash
python tr_sys/manage.py runserver --noreload
```

Preview the message queue at http://localhost:8000/ars/api/messages

Now post a new message to the queue

```bash
curl -d @tr_ars/ars_query.json http://localhost:8000/ars/api/submit
curl -d @tr_sys/tr_ara_unsecret/unsecretStatusQuery.json http://localhost:8000/ars/api/submit
```

Run tests after new code development (also see .travis.yml)

```bash
python server.py test
```

[If desired] manipulate individual agents and their actors to the running ARS server

```bash
python tr_sys/manage.py loaddata ../data/fixtures/channels.json
python tr_sys/manage.py loaddata ../data/fixtures/agents.json
python tr_sys/manage.py loaddata ../data/fixtures/actors.json
curl -d @tr_sys/tr_ars/agent_bte.json http://localhost:8000/ars/api/agents > response1.htm
curl -d @tr_sys/tr_ars/actor_runbte.json http://localhost:8000/ars/api/actors > response2.htm 
curl -d @tr_sys/tr_ara_unsecret/unsecretAgent.json http://localhost:8000/ars/api/agents > response1.htm
curl -d @tr_sys/tr_ara_unsecret/unsecretActor.json http://localhost:8000/ars/api/actors > response2.htm 
```

