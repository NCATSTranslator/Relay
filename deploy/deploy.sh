namespace="ars"

sed -i.bak \
    -e "s/DOCKER_VERSION_VALUE/${BUILD_VERSION}/g" \
    values.yaml
rm values.yaml.bak 

sed -i.bak \
#    -e "s/SECRET_KEY_VALUE/$SECRET_KEY/g" \
    -e "s/ENGINE_VALUE/$ENGINE/g;s/DBNAME_VALUE/$DBNAME/g" \
    -e "s/USERNAME_VALUE/$USERNAME/g;s/PASSWORD_VALUE/$PASSWORD/g" \
    -e "s/HOST_VALUE/$HOST/g;s/PORT_VALUE/$PORT/g" \
    configs/settings.py
rm configs/settings.py.bak    

kubectl apply -f namespace.yaml

# deploy helm chart
helm upgrade --install -n ${namespace} -f values-ncats.yaml ars . 
