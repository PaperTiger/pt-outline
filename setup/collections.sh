#!/usr/bin/env bash
# Creates the ten collections (private, no sharing) and sets group permissions. Safe to re-run: matches on name.
set -euo pipefail
cd "$(dirname "$0")/.."
OWN=$(bin/ol groups.list | jq -r '.data.groups[] | select(.name=="Owners") | .id')
TEAM=$(bin/ol groups.list | jq -r '.data.groups[] | select(.name=="Team") | .id')
EXISTING=$(bin/ol collections.list '{"limit":100}')
jq -c '.[]' setup/collections.json | while read -r c; do
  NAME=$(jq -r .name <<<"$c"); DESC=$(jq -r .description <<<"$c"); TP=$(jq -r .team <<<"$c")
  ID=$(jq -r --arg n "$NAME" '.data[] | select(.name==$n) | .id' <<<"$EXISTING" | head -1)
  if [ -z "$ID" ]; then
    ID=$(bin/ol collections.create "$(jq -nc --arg n "$NAME" --arg d "$DESC" '{name:$n, description:$d, sharing:false}')" | jq -r .data.id)
    echo "created $NAME"
  else
    bin/ol collections.update "$(jq -nc --arg id "$ID" --arg d "$DESC" '{id:$id, description:$d, sharing:false}')" >/dev/null
    echo "exists  $NAME"
  fi
  bin/ol collections.add_group "{\"id\":\"$ID\",\"groupId\":\"$OWN\",\"permission\":\"admin\"}" >/dev/null
  if [ "$TP" = "null" ]; then
    bin/ol collections.remove_group "{\"id\":\"$ID\",\"groupId\":\"$TEAM\"}" >/dev/null || true
  else
    bin/ol collections.add_group "{\"id\":\"$ID\",\"groupId\":\"$TEAM\",\"permission\":\"$TP\"}" >/dev/null
  fi
done
echo; echo "Collection | private | sharing | Owners | Team"
OWN_ID=$OWN TEAM_ID=$TEAM
bin/ol collections.list '{"limit":100}' | jq -c '.data[] | {id, name, permission, sharing}' | while read -r c; do
  ID=$(jq -r .id <<<"$c")
  M=$(bin/ol collections.group_memberships "{\"id\":\"$ID\"}")
  O=$(jq -r --arg g "$OWN_ID" '[.data.groupMemberships[] | select(.groupId==$g) | .permission][0] // "-"' <<<"$M")
  T=$(jq -r --arg g "$TEAM_ID" '[.data.groupMemberships[] | select(.groupId==$g) | .permission][0] // "none"' <<<"$M")
  echo "$(jq -r .name <<<"$c") | $(jq -r 'if .permission==null then "yes" else "NO (\(.permission))" end' <<<"$c") | $(jq -r .sharing <<<"$c") | $O | $T"
done
