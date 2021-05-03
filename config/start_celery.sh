#!/bin/bash

cd /ars/tr_sys
celery -A tr_sys worker -l info
