#!/bin/bash

cd /ars/tr_sys
celery -A tr_sys beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler --detach
celery -A tr_sys worker -l info
