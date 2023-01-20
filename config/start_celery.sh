#!/bin/bash

cd /ars/tr_sys
celery -A tr_sys beat -l info --detach
celery -A tr_sys worker -l info
