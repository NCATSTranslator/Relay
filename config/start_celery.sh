#!/bin/bash

cd /ars/tr_sys
# Start beat with log file
celery -A tr_sys beat -l info -f /var/log/celerybeat.log &
# Start worker in foreground
celery -A tr_sys worker -l info