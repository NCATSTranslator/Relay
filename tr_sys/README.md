ARS implementation
==================

Require python 3+, django 3.0.5+ and channels packages.

```bash
python manage.py makemigrations tr_ars
python manage.py migrate
python manage.py createsuperuser
python manage.py loaddata ../data/fixtures/channels.json
python manage.py loaddata ../data/fixtures/agents.json
python manage.py loaddata ../data/fixtures/actors.json
python manage.py runserver --noreload
```

> You might need to use `python3` command on your system if Python is bound to 2.7

Install dependencies from the [requirements.txt](https://github.com/NCATSTranslator/Relay/blob/master/requirements.txt) in the root of the GitHub repository

```bash
pip install -r ../requirements.txt
```

