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

# replace variables in values.yaml with env vars

CONFIG_HASH="$(shasum settings.py | cut -d ' ' -f 1 | tr -d '\n')"

for item in "${toReplace[@]}";
do
  sed -i.bak \
      -e "s/${item}/${!item}/g" \
      values.yaml
  rm values.yaml.bak
done

# deploy helm chart
helm -n ${namespace} upgrade --install ${projectName} -f values.ci.yaml -f values.ars.yaml ./