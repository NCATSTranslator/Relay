{{/*
Expand the name of the chart.
*/}}
{{- define "ars.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name (63-char limited per DNS naming spec).
*/}}
{{- define "ars.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart name and version as used by the chart label.
*/}}
{{- define "ars.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ars.labels" -}}
helm.sh/chart: {{ include "ars.chart" . }}
{{ include "ars.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels (shared across components; add app.kubernetes.io/component per workload)
*/}}
{{- define "ars.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ars.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Name of the Secret holding all credentials.
*/}}
{{- define "ars.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "ars.fullname" .) }}
{{- end }}
{{- end }}

{{/* ---- dependency coordinates: in-cluster Service DNS or the external value ---- */}}

{{- define "ars.mysqlHost" -}}
{{- if .Values.mysql.enabled }}
{{- printf "%s-mysql" (include "ars.fullname" .) }}
{{- else }}
{{- required "mysql.external.host is required when mysql.enabled=false" .Values.mysql.external.host }}
{{- end }}
{{- end }}

{{- define "ars.mysqlPort" -}}
{{- if .Values.mysql.enabled }}3306{{- else }}{{ .Values.mysql.external.port }}{{- end }}
{{- end }}

{{- define "ars.mysqlDatabase" -}}
{{- if .Values.mysql.enabled }}{{ .Values.mysql.auth.database }}{{- else }}{{ .Values.mysql.external.database }}{{- end }}
{{- end }}

{{- define "ars.mysqlUser" -}}
{{- if .Values.mysql.enabled }}{{ .Values.mysql.auth.username }}{{- else }}{{ .Values.mysql.external.username }}{{- end }}
{{- end }}

{{- define "ars.redisHost" -}}
{{- printf "%s-redis" (include "ars.fullname" .) }}
{{- end }}

{{- define "ars.redisUrl" -}}
{{- if .Values.redis.enabled }}
{{- printf "redis://%s:6379/0" (include "ars.redisHost" .) }}
{{- else }}
{{- required "redis.external.url is required when redis.enabled=false" .Values.redis.external.url }}
{{- end }}
{{- end }}

{{- define "ars.rabbitmqHost" -}}
{{- if .Values.rabbitmq.enabled }}
{{- printf "%s-rabbitmq" (include "ars.fullname" .) }}
{{- else }}
{{- required "rabbitmq.external.host is required when rabbitmq.enabled=false" .Values.rabbitmq.external.host }}
{{- end }}
{{- end }}

{{- define "ars.rabbitmqPort" -}}
{{- if .Values.rabbitmq.enabled }}5672{{- else }}{{ .Values.rabbitmq.external.port }}{{- end }}
{{- end }}

{{- define "ars.rabbitmqUser" -}}
{{- if .Values.rabbitmq.enabled }}{{ .Values.rabbitmq.auth.username }}{{- else }}{{ .Values.rabbitmq.external.username }}{{- end }}
{{- end }}

{{/*
Environment shared by every app container (web, worker, beat, migrate job).
Secrets come in via secretKeyRef; the broker URL is assembled with $(VAR)
expansion so the password never appears in the manifest.
*/}}
{{- define "ars.commonEnv" -}}
- name: ARS_DB_HOST
  value: {{ include "ars.mysqlHost" . | quote }}
- name: ARS_DB_PORT
  value: {{ include "ars.mysqlPort" . | quote }}
- name: ARS_DB_NAME
  value: {{ include "ars.mysqlDatabase" . | quote }}
- name: ARS_DB_USER
  value: {{ include "ars.mysqlUser" . | quote }}
- name: ARS_DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "ars.secretName" . }}
      key: mysql-password
- name: DJANGO_SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "ars.secretName" . }}
      key: django-secret-key
- name: DJANGO_DEBUG
  value: {{ .Values.django.debug | quote }}
- name: POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP
# django.allowedHosts only needs the PUBLIC hostname(s). The in-cluster addresses
# are appended here: kubelet probes reach the pod by IP, and the app calls itself
# by service name (see ARS_DEFAULT_HOST below). Django rejects any Host header not
# in this list with DisallowedHost, which would fail the readiness probe forever.
- name: DJANGO_ALLOWED_HOSTS
  value: "{{ .Values.django.allowedHosts }},{{ include "ars.fullname" . }},{{ include "ars.fullname" . }}.{{ .Release.Namespace }}.svc.cluster.local,localhost,127.0.0.1,$(POD_IP)"
- name: DJANGO_LOG_LEVEL
  value: {{ .Values.django.logLevel | quote }}
- name: RABBITMQ_USER
  value: {{ include "ars.rabbitmqUser" . | quote }}
- name: RABBITMQ_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "ars.secretName" . }}
      key: rabbitmq-password
- name: CELERY_BROKER_URL
  value: "amqp://$(RABBITMQ_USER):$(RABBITMQ_PASSWORD)@{{ include "ars.rabbitmqHost" . }}:{{ include "ars.rabbitmqPort" . }}//"
- name: REDIS_URL
  value: {{ include "ars.redisUrl" . | quote }}
- name: ARS_REDIS_HOST
  value: {{ include "ars.redisHost" . | quote }}
- name: AES_MASTER_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "ars.secretName" . }}
      key: aes-master-key
# Base URL the ARS uses to reach ITSELF. Two things are built from it (tr_ars/tasks.py):
#   1. outbound: agent URIs are relative ("/ara-aragorn/api/"), so this + the path
#      hits this deployment's own per-agent proxy views, which forward to the real ARA;
#   2. the callback URL handed to each ARA so it can POST results back -- and
#      default_ars_app/api.py forwards that callback verbatim to the ARA.
# Because of (2) the ARAs must be able to resolve this address. The default is the
# cluster-internal FQDN, which resolves from ANY namespace in the cluster (a bare
# service name only resolves within this one, so ARAs in another namespace would
# silently fail to call back and every child would sit at Running until
# catch_timeout marks it 598). For ARAs outside the cluster set django.defaultHost
# to the public URL instead -- it is one or the other, not both.
- name: ARS_DEFAULT_HOST
  value: {{ .Values.django.defaultHost | default (printf "http://%s.%s.svc.cluster.local:%v" (include "ars.fullname" .) .Release.Namespace .Values.service.port) | quote }}
- name: ARS_EXPENSIVE_LIMIT
  value: {{ .Values.expensiveGate.limit | quote }}
- name: ARS_EXPENSIVE_LEASE_MS
  value: {{ .Values.expensiveGate.leaseMs | quote }}
- name: ARS_EXPENSIVE_RENEW_SEC
  value: {{ .Values.expensiveGate.renewSec | quote }}
- name: ARS_EXPENSIVE_ZKEY
  value: {{ .Values.expensiveGate.zkey | quote }}
- name: ARS_EXPENSIVE_TASK_MAX_RETRIES
  value: {{ .Values.expensiveGate.taskMaxRetries | quote }}
- name: ARS_MERGE_ERROR_MAX_RETRIES
  value: {{ .Values.merge.errorMaxRetries | quote }}
- name: JAEGER_HOST
  value: {{ .Values.otel.jaegerHost | quote }}
- name: JAEGER_PORT
  value: {{ .Values.otel.jaegerPort | quote }}
{{- range $key, $value := .Values.env }}
- name: {{ $key }}
  value: {{ $value | quote }}
{{- end }}
{{- with .Values.extraEnv }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Pod scheduling knobs shared by every pod in the release.
*/}}
{{- define "ars.podScheduling" -}}
{{- with .Values.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.nodeSelector }}
nodeSelector:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.affinity }}
affinity:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- with .Values.tolerations }}
tolerations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
The settings.py volume + a checksum helper for pod-restart-on-change.
*/}}
{{- define "ars.settingsChecksum" -}}
{{ .Files.Get "files/settings.py" | sha256sum }}
{{- end }}
