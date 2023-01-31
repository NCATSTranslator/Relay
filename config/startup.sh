#!/bin/bash


# makemigrations command is changed to run locally and commit migrations file into github repo
#python tr_sys/manage.py makemigrations tr_ars
python tr_sys/manage.py migrate --fake tr_ars 0006_message_result_stat
python tr_sys/manage.py migrate --fake tr_ars 0007_auto_20230131_1846
python tr_sys/manage.py migrate
#python tr_sys/manage.py createsuperuser
