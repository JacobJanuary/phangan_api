#!/usr/bin/env bash
# Deploy a commit of phangan_api to fc-api as a new release.
#
# The release is `git archive` of the commit, never the worktree, and keeps
# the hash in REVISION. `current` is switched to it and the container
# rebuilt; the previous release is printed for rollback (point `current`
# back at it, then `docker compose build api` and `sudo docker compose up -d api`).
#
# Usage: scripts/deploy_fc_api.sh [ref]     (default HEAD)
set -euo pipefail

ref="${1:-HEAD}"
host="${DEPLOY_HOST:-fc-api}"
root=/srv/phangan/api

cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Uncommitted changes in tracked files: commit them, the release is built from git." >&2
  exit 1
fi
sha=$(git rev-parse --verify "${ref}^{commit}")
release=$(date -u +%Y%m%d_%H%M%S)
echo "Deploying ${sha:0:7} as release ${release} to ${host}"

git archive --format=tar "$sha" | ssh "$host" "set -e
  sudo -n mkdir '$root/releases/$release'
  sudo -n tar xf - -C '$root/releases/$release' --no-same-owner
  echo '$sha' | sudo -n tee '$root/releases/$release/REVISION' >/dev/null"

ssh "$host" "set -e
  cd '$root'
  echo \"previous release: \$(readlink current)\"
  sudo -n ln -sfn '$root/releases/$release' current.new
  sudo -n mv -T current.new current
  docker compose -f compose.yml build api >/dev/null
  sudo -n docker compose -f compose.yml up -d api"

status=starting
for _ in $(seq 1 45); do
  status=$(ssh "$host" "docker inspect -f '{{.State.Health.Status}}' phangan-api")
  [ "$status" = healthy ] && break
  sleep 2
done
echo "phangan-api: ${status} (release ${release}, ${sha:0:7})"
[ "$status" = healthy ]
