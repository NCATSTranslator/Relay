#!/bin/bash

# variables 
projectName="ars"
namespace="ars"
# replace place_holder with values from env var
# env var's key needs to be the same as the place_holder
toReplace=('BUILD_VERSION')

# export .env values to env vars
# export $(egrep -v '^#' .env)

# printenv

sed -i.bak \
    -e "s/ARS_ALLOWED_HOSTS_VALUE/${ARS_ALLOWED_HOSTS}/g" \
    -e "s/ARS_DATABASE_VALUE/${ARS_DATABASE}/g" \
    -e "s/ARS_DB_USER_VALUE/${ARS_DB_USER}/g" \
    -e "s/ARS_DB_PASSWORD_VALUE/${ARS_DB_PASSWORD}/g" \
    -e "s/ARS_DB_HOST_VALUE/${ARS_DB_HOST}/g" \
    -e "s/ARS_DJANGO_SECRET_KEY_VALUE/${ARS_DJANGO_SECRET_KEY}/g" \
    -e "s/ARS_SETTINGS_DEFAULT_HOST_VALUE/${ARS_SETTINGS_DEFAULT_HOST}/g" \
    settings.py
rm settings.py.bak

# CONFIG_HASH="$(shasum settings.py | cut -d ' ' -f 1 | tr -d '\n')"

# sed -i.bak \
#    -e "s/CONFIG_HASH_VALUE/${CONFIG_HASH}/g" \
#    deployment.yaml
# rm deployment.yaml.bak

# replace variables in values.yaml with env vars

for item in "${toReplace[@]}";
do
  sed -i.bak \
      -e "s/${item}/${!item}/g" \
      values.yaml
  rm values.yaml.bak
done

kubectl apply -f namespace.yaml

# deploy helm chart
helm upgrade --install -n ${namespace} -f values-ci.yaml -f values.yaml ars . 
