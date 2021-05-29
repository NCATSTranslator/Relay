#!/bin/bash

export $(egrep -v '^#' .env)

sed -i.bak \
    -e "s/ALLOWED_HOSTS_VALUE/${ARS_HOSTNAME}/g" \
    -e "s/ARS_DATABASE_VALUE/${ARS_DATABASE}/g" \
    -e "s/ARS_DB_USER_VALUE/${ARS_DB_USER}/g" \
    -e "s/ARS_DB_PASSWORD_VALUE/${ARS_DB_PASSWORD}/g" \
    -e "s/ARS_DB_HOST_VALUE/${ARS_DB_HOST}/g" \
    settings.py
rm settings.py.bak

CONFIG_HASH="$(shasum settings.py | cut -d ' ' -f 1 | tr -d '\n')"

sed -i.bak \
    -e "s/CONFIG_HASH_VALUE/${CONFIG_HASH}/g" \
    -e "s/DOCKER_VERSION_VALUE/${BUILD_VERSION}/g" \
    deployment.yaml
rm deployment.yaml.bak

sed -i.bak \
    -e "s/ARS_HOSTNAME_VALUE/${ARS_HOSTNAME}/g" \
    -e "s/ARS_ALB_TAG_VALUE/${ARS_ALB_TAG}/g" \
    -e "s/ARS_ALB_SG_VALUE/${ARS_ALB_SG}/g" \
    -e "s/ENVIRONMENT_TAG_VALUE/${ENVIRONMENT_TAG}/g" \
    ingress.yaml
rm ingress.yaml.bak

kubectl apply -f namespace.yaml
kubectl delete configmap ars-config -n ars
kubectl create configmap ars-config -n ars --from-file=settings.py --dry-run -o yaml | kubectl apply -f -
kubectl apply -f deployment.yaml
kubectl apply -f services.yaml
kubectl apply -f ingress.yaml
