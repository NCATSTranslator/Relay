#!/bin/bash


# makemigrations command is changed to run locally and commit migrations file into github repo
#python tr_sys/manage.py makemigrations tr_ars

python tr_sys/manage.py migrate
#python tr_sys/manage.py createsuperuser
