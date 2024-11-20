FROM python:3.9-buster

ENV PYTHONUNBUFFERED=1
#newRelic changes
ARG NEWRELIC_KEY
WORKDIR /ars
RUN apt-get update && apt install -y netcat
#newRelic changes
RUN pip install --no-cache-dir newrelic
RUN newrelic-admin generate-config $NEWRELIC_KEY newrelic.ini

COPY requirements.txt /ars/
RUN pip install -r requirements.txt
COPY . /ars/
RUN mv wait-for /bin/wait-for
