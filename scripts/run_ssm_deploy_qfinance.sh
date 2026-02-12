#!/usr/bin/env bash
set -euo pipefail

# Run QFinance deploy+verify in EC2 through AWS SSM Run Command.
# Defaults match the production environment used by this repository.

REGION="${REGION:-us-west-1}"
INSTANCE_ID="${INSTANCE_ID:-i-034f57c3aaaf1f786}"
LOG_GROUP="${LOG_GROUP:-/ssm/qfinance/runcommand}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[ERROR] Missing required command: $1" >&2
    exit 2
  }
}

require_cmd aws
require_cmd jq
require_cmd base64

echo "== Identity =="
aws sts get-caller-identity --region "${REGION}" --output json

echo "== PingStatus =="
PING_STATUS="$(aws ssm describe-instance-information \
  --region "${REGION}" \
  --filters "Key=InstanceIds,Values=${INSTANCE_ID}" \
  --query 'InstanceInformationList[0].PingStatus' \
  --output text)"
echo "PingStatus=${PING_STATUS}"
[[ "${PING_STATUS}" == "Online" ]] || {
  echo "[ERROR] Instance ${INSTANCE_ID} is not Online in SSM." >&2
  exit 10
}

echo "== CloudWatch Logs group =="
aws logs create-log-group --region "${REGION}" --log-group-name "${LOG_GROUP}" >/dev/null 2>&1 || true
aws logs put-retention-policy --region "${REGION}" --log-group-name "${LOG_GROUP}" --retention-in-days 7

read -r -d '' REMOTE_SCRIPT <<'EOS' || true
set -euo pipefail

CANDIDATES=(
  "$HOME/qfinance_git"
  "$HOME/qfinance"
  "/workspace/qfinance_git"
  "/workspace/qfinance"
)

REPO_DIR=""
for d in "${CANDIDATES[@]}"; do
  if [ -d "$d/.git" ] && (cd "$d" && git remote -v | awk '{print $1}' | grep -qx origin); then
    REPO_DIR="$d"
    break
  fi
done

[ -n "$REPO_DIR" ] || {
  echo "ERROR: no repo with origin found"
  exit 20
}

echo "USING_REPO=$REPO_DIR"
cd "$REPO_DIR"

git remote -v
git fetch --all --prune

if git ls-remote --heads origin main | grep -q 'refs/heads/main'; then
  git checkout -B main origin/main
else
  git checkout -B master origin/master
fi

git pull --ff-only
echo "DEPLOYING_COMMIT=$(git rev-parse --short HEAD)"

ENABLE_SWAP=0 scripts/deploy_frontend_ec2.sh

set +e
scripts/verify_ec2_release.sh
VERIFY_EXIT_CODE=$?
set -e
echo "VERIFY_EXIT_CODE=${VERIFY_EXIT_CODE}"

sudo ss -lntp | grep -E '(:8088|:8000)' || true

[[ "${VERIFY_EXIT_CODE}" == "0" ]] || exit "${VERIFY_EXIT_CODE}"
EOS

REMOTE_B64="$(printf '%s' "${REMOTE_SCRIPT}" | base64 | tr -d '\n')"

read -r -d '' COMMAND_STAGE <<EOS || true
cat >/tmp/qfinance-remote.b64 <<'B64'
${REMOTE_B64}
B64
EOS

COMMAND_DECODE="base64 -d /tmp/qfinance-remote.b64 >/tmp/qfinance-remote.sh"
COMMAND_EXEC="sudo -iu ubuntu bash /tmp/qfinance-remote.sh"

jq -n \
  --arg iid "${INSTANCE_ID}" \
  --arg lg "${LOG_GROUP}" \
  --arg c1 "${COMMAND_STAGE}" \
  --arg c2 "${COMMAND_DECODE}" \
  --arg c3 "${COMMAND_EXEC}" \
  '{
    DocumentName:"AWS-RunShellScript",
    Comment:"qfinance deploy+verify via ssm run command (bash -lc)",
    InstanceIds:[$iid],
    CloudWatchOutputConfig:{CloudWatchOutputEnabled:true,CloudWatchLogGroupName:$lg},
    Parameters:{commands:[$c1,$c2,$c3]}
  }' > /tmp/ssm-qfinance-send.json

echo "== send-command =="
COMMAND_ID="$(aws ssm send-command \
  --region "${REGION}" \
  --cli-input-json file:///tmp/ssm-qfinance-send.json \
  --query 'Command.CommandId' \
  --output text)"

echo "COMMAND_ID=${COMMAND_ID}"

echo "== polling status =="
FINAL_STATUS=""
for i in $(seq 1 180); do
  STATUS="$(aws ssm get-command-invocation \
    --region "${REGION}" \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --query 'Status' \
    --output text 2>/dev/null || true)"
  RC="$(aws ssm get-command-invocation \
    --region "${REGION}" \
    --command-id "${COMMAND_ID}" \
    --instance-id "${INSTANCE_ID}" \
    --query 'ResponseCode' \
    --output text 2>/dev/null || true)"
  echo "poll=${i} status=${STATUS:-NA} response_code=${RC:-NA}"

  case "${STATUS}" in
    Success|Failed|Cancelled|TimedOut|Undeliverable|Terminated|ExecutionTimedOut)
      FINAL_STATUS="${STATUS}"
      break
      ;;
  esac
  sleep 5
done

[[ -n "${FINAL_STATUS}" ]] || {
  echo "[ERROR] Polling timeout without terminal status." >&2
  exit 30
}

INVOC_JSON="$(aws ssm get-command-invocation \
  --region "${REGION}" \
  --command-id "${COMMAND_ID}" \
  --instance-id "${INSTANCE_ID}" \
  --output json)"

echo "FINAL_STATUS=${FINAL_STATUS}"
echo "${INVOC_JSON}" | jq -r '"Status=\(.Status) ResponseCode=\(.ResponseCode)"'
echo "----- STDOUT -----"
echo "${INVOC_JSON}" | jq -r '.StandardOutputContent'
echo "----- STDERR -----"
echo "${INVOC_JSON}" | jq -r '.StandardErrorContent'

DEPLOYING_COMMIT="$(echo "${INVOC_JSON}" | jq -r '.StandardOutputContent' | sed -n 's/^DEPLOYING_COMMIT=//p' | tail -n1)"
VERIFY_EXIT_CODE="$(echo "${INVOC_JSON}" | jq -r '.StandardOutputContent' | sed -n 's/^VERIFY_EXIT_CODE=//p' | tail -n1)"

echo "DEPLOYING_COMMIT=${DEPLOYING_COMMIT:-N/A}"
echo "VERIFY_EXIT_CODE=${VERIFY_EXIT_CODE:-N/A}"
echo "CLOUDWATCH_LOG_GROUP=${LOG_GROUP}"
echo "TIP: log stream prefix usually includes ${COMMAND_ID}/${INSTANCE_ID}"

[[ "${FINAL_STATUS}" == "Success" ]] || exit 40
[[ "${VERIFY_EXIT_CODE:-1}" == "0" ]] || exit 41

echo "OK: Deploy+Verify completado por SSM. CommandId=${COMMAND_ID}"
