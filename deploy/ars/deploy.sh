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

CONFIG_HASH="$(shasum configs/settings.py | cut -d ' ' -f 1 | tr -d '\n')"

  sed -i.bak \
     -e "s/CONFIG_HASH_VALUE/${CONFIG_HASH}/g" \
    templates/deployment.yaml
  rm templates/deployment.yaml.bak

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
