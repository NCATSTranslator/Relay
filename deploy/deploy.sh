namespace="ars"

sed -i.bak \
    -e "s/DOCKER_VERSION_VALUE/${BUILD_VERSION}/g" \
    values.yaml
rm values.yaml.bak

sed -i.bak \
    -e "s/USERNAME_VALUE/$USERNAME/g;s/PASSWORD_VALUE/$PASSWORD/g" \
    -e "s/ENGINE_VALUE/$ENGINE/g;s/DEFAULT_HOST_VALUE/$DEFAULT_HOST/g" \
    -e "s/DBNAME_VALUE/$DBNAME/g;s/HOST_VALUE/$HOST/g" \
    -e "s/PORT_VALUE/$PORT/g;s/SECRET_KEY_VALUE/$SECRET_KEY/g" \
    -e "s/CSRF_TRUSTED_ORIGINS_VALUE/$CSRF_TRUSTED_ORIGINS/g" \
    configs/settings.py
rm configs/settings.py.bak    

kubectl apply -f namespace.yaml

# deploy helm chart
helm upgrade --install -n ${namespace} -f values-ncats.yaml ars . 
