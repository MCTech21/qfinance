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
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
ENABLE_SWAP="${ENABLE_SWAP:-0}"
MIN_FREE_MB="${MIN_FREE_MB:-350}"
RESTART_BACKEND="${RESTART_BACKEND:-1}"
BACKEND_SERVICE_CANDIDATES="${BACKEND_SERVICE_CANDIDATES:-}"
BACKEND_RESTART_COMMAND="${BACKEND_RESTART_COMMAND:-}"
BACKEND_VERIFY_PATH="${BACKEND_VERIFY_PATH:-}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "[ERROR] Falta comando requerido: $1" >&2; exit 1; }
}

shell_escape() {
  printf '%q' "$1"
}

to_b64() {
  printf '%s' "$1" | base64 | tr -d '\n'
}

build_remote_payload() {
  local q_work_dir q_repo_url q_branch
  local web_url_b64 backend_url_b64 enable_swap_b64 min_free_mb_b64 restart_backend_b64
  local backend_service_candidates_b64 backend_restart_command_b64 backend_verify_path_b64

  q_work_dir=$(shell_escape "${EC2_WORK_DIR}")
  q_repo_url=$(shell_escape "${REPO_URL}")
  q_branch=$(shell_escape "${BRANCH}")

  web_url_b64=$(to_b64 "${WEB_URL}")
  backend_url_b64=$(to_b64 "${BACKEND_URL}")
  enable_swap_b64=$(to_b64 "${ENABLE_SWAP}")
  min_free_mb_b64=$(to_b64 "${MIN_FREE_MB}")
  restart_backend_b64=$(to_b64 "${RESTART_BACKEND}")
  backend_service_candidates_b64=$(to_b64 "${BACKEND_SERVICE_CANDIDATES}")
  backend_restart_command_b64=$(to_b64 "${BACKEND_RESTART_COMMAND}")
  backend_verify_path_b64=$(to_b64 "${BACKEND_VERIFY_PATH}")

  cat <<REMOTE
set -euo pipefail
if [[ ! -d ${q_work_dir}/.git ]]; then
  mkdir -p "\$(dirname ${q_work_dir})"
  git clone --depth 1 --branch ${q_branch} ${q_repo_url} ${q_work_dir}
else
  git -C ${q_work_dir} fetch --all --prune
  git -C ${q_work_dir} checkout ${q_branch}
  git -C ${q_work_dir} reset --hard origin/${q_branch}
  git -C ${q_work_dir} clean -fd
fi

decode_b64() { printf '%s' "\$1" | base64 -d; }
WEB_URL="\$(decode_b64 '${web_url_b64}')"
BACKEND_URL="\$(decode_b64 '${backend_url_b64}')"
ENABLE_SWAP="\$(decode_b64 '${enable_swap_b64}')"
MIN_FREE_MB="\$(decode_b64 '${min_free_mb_b64}')"
RESTART_BACKEND="\$(decode_b64 '${restart_backend_b64}')"
BACKEND_SERVICE_CANDIDATES="\$(decode_b64 '${backend_service_candidates_b64}')"
BACKEND_RESTART_COMMAND="\$(decode_b64 '${backend_restart_command_b64}')"
BACKEND_VERIFY_PATH="\$(decode_b64 '${backend_verify_path_b64}')"

echo "[INFO] CloudShell->EC2 vars: BACKEND_URL=\${BACKEND_URL} BACKEND_VERIFY_PATH=\${BACKEND_VERIFY_PATH} RESTART_BACKEND=\${RESTART_BACKEND}"
if [[ -n "\${BACKEND_RESTART_COMMAND}" ]]; then
  echo "[INFO] CloudShell->EC2 restart command recibido."
else
  echo "[WARN] CloudShell->EC2 restart command vacío."
fi

WEB_URL="\${WEB_URL}" BACKEND_URL="\${BACKEND_URL}" ENABLE_SWAP="\${ENABLE_SWAP}" MIN_FREE_MB="\${MIN_FREE_MB}" BRANCH=${q_branch} EC2_WORK_DIR=${q_work_dir} REPO_URL=${q_repo_url} RESTART_BACKEND="\${RESTART_BACKEND}" BACKEND_SERVICE_CANDIDATES="\${BACKEND_SERVICE_CANDIDATES}" BACKEND_RESTART_COMMAND="\${BACKEND_RESTART_COMMAND}" BACKEND_VERIFY_PATH="\${BACKEND_VERIFY_PATH}" bash ${q_work_dir}/scripts/ec2_sync_and_deploy.sh
REMOTE
}

remote_payload="$(build_remote_payload)"
remote_payload_compact="${remote_payload//$'\n'/; }"

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
  ssh "${ssh_opts[@]}" "${EC2_USER}@${EC2_HOST}" "bash -lc $(shell_escape "${remote_payload}")"
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
    --parameters "commands=[\"${remote_payload_compact}\"]" \
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
