{{- define "hw11.labels" -}}
app.kubernetes.io/name: hw11
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
