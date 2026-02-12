#!/usr/bin/env bash
set -euo pipefail

# CloudShell orchestrator (EC2-first): NO build/git pesado local.

DEPLOY_TRANSPORT="${DEPLOY_TRANSPORT:-ssh}" # ssh|ssm
EC2_HOST="${EC2_HOST:-}"
EC2_USER="${EC2_USER:-ubuntu}"
EC2_SSH_PORT="${EC2_SSH_PORT:-22}"
EC2_SSH_KEY="${EC2_SSH_KEY:-}"
EC2_INSTANCE_ID="${EC2_INSTANCE_ID:-}"
EC2_WORK_DIR="${EC2_WORK_DIR:-/opt/qfinance_git}"
REPO_URL="${REPO_URL:-git@github.com:MCTech21/qfinance.git}"
BRANCH="${BRANCH:-main}"
WEB_URL="${WEB_URL:-http://127.0.0.1:8088}"
ENABLE_SWAP="${ENABLE_SWAP:-0}"
VERIFY_SEED_ENDPOINT="${VERIFY_SEED_ENDPOINT:-1}"
MIN_FREE_MB="${MIN_FREE_MB:-350}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] Falta comando requerido: $1" >&2; exit 1; }
}

remote_payload="WEB_URL='${WEB_URL}' ENABLE_SWAP='${ENABLE_SWAP}' MIN_FREE_MB='${MIN_FREE_MB}' VERIFY_SEED_ENDPOINT='${VERIFY_SEED_ENDPOINT}' BRANCH='${BRANCH}' EC2_WORK_DIR='${EC2_WORK_DIR}' REPO_URL='${REPO_URL}' bash '${EC2_WORK_DIR}/scripts/ec2_sync_and_deploy.sh'"

run_ssh() {
  require_cmd ssh
  [[ -n "${EC2_HOST}" ]] || { echo "[ERROR] EC2_HOST es requerido para DEPLOY_TRANSPORT=ssh" >&2; exit 1; }

  local ssh_opts=(-p "${EC2_SSH_PORT}" -o ServerAliveInterval=30 -o ServerAliveCountMax=5)
  if [[ -n "${EC2_SSH_KEY}" ]]; then
    ssh_opts+=(-i "${EC2_SSH_KEY}")
  fi

  echo "[INFO] Validando conectividad SSH a ${EC2_USER}@${EC2_HOST}:${EC2_SSH_PORT} ..."
  ssh "${ssh_opts[@]}" "${EC2_USER}@${EC2_HOST}" "echo '[OK] SSH reachability confirmada'"

  echo "[INFO] Ejecutando deploy EC2-first vía SSH ..."
  ssh "${ssh_opts[@]}" "${EC2_USER}@${EC2_HOST}" "bash -lc \"${remote_payload}\""
}

run_ssm() {
  require_cmd aws
  [[ -n "${EC2_INSTANCE_ID}" ]] || { echo "[ERROR] EC2_INSTANCE_ID es requerido para DEPLOY_TRANSPORT=ssm" >&2; exit 1; }

  echo "[INFO] Validando conectividad SSM para instance ${EC2_INSTANCE_ID} ..."
  aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=${EC2_INSTANCE_ID}" \
    --query 'InstanceInformationList[0].PingStatus' \
    --output text | grep -Eq 'Online|ConnectionLost' || {
      echo "[ERROR] La instancia no aparece como gestionada por SSM." >&2
      exit 1
    }

  echo "[INFO] Ejecutando deploy EC2-first vía SSM ..."
  local cmd_id
  cmd_id=$(aws ssm send-command \
    --instance-ids "${EC2_INSTANCE_ID}" \
    --document-name "AWS-RunShellScript" \
    --comment "qfinance ec2-first deploy" \
    --parameters "commands=[\"${remote_payload}\"]" \
    --query 'Command.CommandId' \
    --output text)

  echo "[INFO] COMMAND_ID=${cmd_id}"
  aws ssm wait command-executed --command-id "${cmd_id}" --instance-id "${EC2_INSTANCE_ID}"

  local status
  status=$(aws ssm get-command-invocation --command-id "${cmd_id}" --instance-id "${EC2_INSTANCE_ID}" --query 'Status' --output text)
  echo "[INFO] FINAL_STATUS=${status}"

  aws ssm get-command-invocation --command-id "${cmd_id}" --instance-id "${EC2_INSTANCE_ID}" --query 'StandardOutputContent' --output text
  if [[ "${status}" != "Success" ]]; then
    echo "[ERROR] Deploy vía SSM falló." >&2
    aws ssm get-command-invocation --command-id "${cmd_id}" --instance-id "${EC2_INSTANCE_ID}" --query 'StandardErrorContent' --output text >&2 || true
    exit 1
  fi
}

case "${DEPLOY_TRANSPORT}" in
  ssh)
    run_ssh
    ;;
  ssm)
    run_ssm
    ;;
  *)
    echo "[ERROR] DEPLOY_TRANSPORT inválido: ${DEPLOY_TRANSPORT} (usa ssh|ssm)" >&2
    exit 1
    ;;
esac

echo "[OK] CloudShell orchestration finalizada (EC2-first)."
