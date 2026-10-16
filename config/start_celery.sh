#!/bin/bash

cd /ars/tr_sys
# Start beat with log file
celery -A tr_sys beat -l info -f /var/log/celerybeat.log &
# Start worker in foreground. Single-worker deployments (docker-compose, the
# legacy deploy/ chart) must consume BOTH queues: merge-and-post-process and
# ingest-ara-response are routed to `heavy` (tr_sys/celery.py task_routes) and
# would otherwise sit in RabbitMQ with no consumer. helm/ars runs a separate
# worker pool per queue instead.
celery -A tr_sys worker -l info -Q celery,heavy --concurrency=10 --prefetch-multiplier=1

