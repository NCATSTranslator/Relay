namespace="ars"

export $(egrep -v '^#' .env)

CONFIG_HASH="$(shasum configs/settings.py | cut -d ' ' -f 1 | tr -d '\n')"

sed -i.bak \
    -e "s/CONFIG_HASH_VALUE/${CONFIG_HASH}/g" \
    templates/deployment.yaml
rm templates/deployment.yaml.bak

sed -i.bak \
    -e "s/DOCKER_VERSION_VALUE/${BUILD_VERSION}/g" \
    values.yaml
rm values.yaml.bak

kubectl apply -f namespace.yaml

# deploy helm chart
helm upgrade --install -n ${namespace} -f values-ci.yaml ars . 
