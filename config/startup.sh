#!/bin/bash

sleep 10s
python tr_sys/manage.py makemigrations tr_ars
python tr_sys/manage.py migrate
#python tr_sys/manage.py createsuperuser
