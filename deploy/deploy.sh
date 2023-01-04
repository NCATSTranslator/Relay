namespace="ars"

sed -i.bak \
    -e "s/DOCKER_VERSION_VALUE/${BUILD_VERSION}/g" \
    values.yaml
rm values.yaml.bak 

kubectl apply -f namespace.yaml

# deploy helm chart
helm upgrade --install -n ${namespace} -f values-ncats.yaml ars . 
