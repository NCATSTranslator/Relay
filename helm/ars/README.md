# ars (self-contained dev chart)

A Helm chart that deploys the ARS **and all of its backing services** — MySQL
and RabbitMQ — so a dev instance comes up on any Kubernetes cluster with
no externally supplied files. It is the outcome of `deploy/HELM_DEPENDENCIES.md`;
the Jenkins-driven production chart in `deploy/` is untouched.

Differences from `deploy/`:

| | `deploy/` | `helm/ars/` |
|---|---|---|
| Topology | one pod, 4 containers over `localhost` | one pod per component (server / heavy worker / light worker / beat / mysql / rabbitmq) |
| MySQL | external, invisible to the chart | in-cluster StatefulSet + PVC by default, or `mysql.enabled=false` + `mysql.external.*` |
| RabbitMQ | sidecar, no volume | own pod with a PVC (celery is configured for persistent delivery) |
| Redis | sidecar (token gate + unused Channels layer) | gone; nothing in the app uses it anymore |
| `settings.py` | injected by Jenkins, `sed`-substituted | in the chart (`files/settings.py`), reads env vars; credentials via a Secret |
| Migrations | `manage.py migrate` in the server container command | post-install/post-upgrade hook Job |
| Celery beat | started inside the worker script | own single-replica Deployment |
| Scaling | impossible (replicating the pod duplicates the broker) | `arsserver.replicas` / `celeryworkers.<pool>.replicas` |

## Quick start (kind / minikube / any dev cluster)

```sh
# 1. Build the app image and make it available to the cluster
docker build -t relay_ars:latest .
kind load docker-image relay_ars:latest        # or: minikube image load relay_ars:latest

# 2. Install
helm install ars ./helm/ars -n ars --create-namespace

# 3. Talk to it
kubectl -n ars port-forward svc/ars 8000:80
curl http://localhost:8000/ars/api/health
```

On a cluster with ECR access, skip the build and use the CI image:

```sh
helm install ars ./helm/ars -n ars --create-namespace \
  --set image.repository=853771734544.dkr.ecr.us-east-1.amazonaws.com/translator-ars \
  --set image.tag=<version> --set image.pullPolicy=Always
```

## Using external backing services

```yaml
mysql:
  enabled: false
  external:
    host: my-rds.cluster-xyz.us-east-1.rds.amazonaws.com
    port: 3306
    database: arsdb
    username: ars
```

Passwords always come from the release Secret — set `secrets.mysqlPassword`
etc., or point `secrets.existingSecret` at a Secret you manage (keys:
`django-secret-key`, `aes-master-key`, `mysql-root-password`, `mysql-password`,
`rabbitmq-password`).

## Notes and limits

- **Dev credentials ship in `values.yaml`.** Override every `secrets.*` value
  (or use `secrets.existingSecret`) for any instance others can reach.
- The in-cluster MySQL is a single node with no backups — fine for dev, not for
  anything you'd miss.
- The external Translator services (`env.TR_ANNOTATOR`, `env.TR_APPRAISE`)
  default to the public CI endpoints; queries fan out to the
  live ARAs/KPs selected by `env.TR_ENV` (SmartAPI maturity level).
- OTEL trace export points at `otel.jaegerHost`; if no collector exists at that
  address the exporter logs connection errors and the app carries on.
- `affinity`/`tolerations` are empty by default so pods schedule anywhere; copy
  the node pinning from `deploy/values.yaml` if an environment needs it.
