# Deploy por AWS SSM desde CloudShell (sin SSH)

Este runbook evita SSH/.pem y ejecuta deploy + verify usando SSM Run Command.

## 1) Preparación en CloudShell

```bash
cd ~
if [ -d qfinance_git/.git ]; then
  cd qfinance_git
elif [ -d qfinance/.git ]; then
  cd qfinance
else
  # Usa la URL del botón "Code" (HTTPS o SSH)
  git clone <REPO_URL> qfinance_git
  cd qfinance_git
fi

git fetch --all --prune
git checkout main || git checkout master
git pull --ff-only
```

## 2) Ejecutar deploy SSM

```bash
bash run_ssm_deploy_qfinance.sh
```

Si estás fuera del repo y quieres un único comando:

```bash
REPO_URL=<REPO_URL> bash scripts/cloudshell_bootstrap_ssm_deploy.sh
```

## 3) Resultado esperado

Al finalizar, valida que el runner imprima:

- `COMMAND_ID=...`
- `FINAL_STATUS=Success`
- `DEPLOYING_COMMIT=...`
- `VERIFY_EXIT_CODE=0`
- `CLOUDWATCH_LOG_GROUP=/ssm/qfinance/runcommand`

## Troubleshooting

### Error: `No such file or directory`

Estás fuera del checkout del repo.

```bash
pwd
ls -la
# Si no ves README.md y scripts/, aún no estás dentro del repo.
```

### Error: `Invalid JSON received`

Usa el runner del repo (`run_ssm_deploy_qfinance.sh`), que construye el payload con `jq` para evitar JSON roto.

### Error: `Invalid endpoint: https://ssm..amazonaws.com`

Asegura región válida y no vacía:

```bash
export REGION=us-west-1
```


### Si GitHub marca conflicto en `README.md` antes de actualizar rama

No aceptes ambos bloques si duplican instrucciones. Mantén la versión que:

1. Conserva el enlace a `docs/cloudshell_ssm_deploy.md`.
2. Evita duplicar runbooks largos dentro del `README.md`.
3. Deja intacto el checklist de `.env` no versionados.

### Ver logs completos de SSM en CloudWatch

El comando envía salida completa a:

- Log Group: `/ssm/qfinance/runcommand`
- Stream: normalmente incluye `COMMAND_ID/INSTANCE_ID`
