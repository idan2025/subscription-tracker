{{/*
Expand the name of the chart.
*/}}
{{- define "subscription-tracker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "subscription-tracker.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "subscription-tracker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "subscription-tracker.labels" -}}
helm.sh/chart: {{ include "subscription-tracker.chart" . }}
{{ include "subscription-tracker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "subscription-tracker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "subscription-tracker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Flask labels
*/}}
{{- define "subscription-tracker.flask.labels" -}}
{{ include "subscription-tracker.labels" . }}
app: {{ .Values.flask.name }}
{{- end }}

{{/*
Flask selector labels
*/}}
{{- define "subscription-tracker.flask.selectorLabels" -}}
{{ include "subscription-tracker.selectorLabels" . }}
app: {{ .Values.flask.name }}
{{- end }}

{{/*
MySQL labels
*/}}
{{- define "subscription-tracker.mysql.labels" -}}
{{ include "subscription-tracker.labels" . }}
app: mysql
{{- end }}

{{/*
MySQL selector labels
*/}}
{{- define "subscription-tracker.mysql.selectorLabels" -}}
{{ include "subscription-tracker.selectorLabels" . }}
app: mysql
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "subscription-tracker.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "subscription-tracker.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the proper image name
*/}}
{{- define "subscription-tracker.flask.image" -}}
{{- printf "%s:%s" .Values.flask.image.repository .Values.flask.image.tag }}
{{- end }}

{{/*
Return the proper MySQL image name
*/}}
{{- define "subscription-tracker.mysql.image" -}}
{{- printf "%s:%s" .Values.mysql.image.repository .Values.mysql.image.tag }}
{{- end }}
