#!/usr/bin/env bash

set -euo pipefail
IFS=$'\n\t'
SCRIPT_FOLDER="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

ORG_GH_NAME="${1}"

org_field() {
  local field_name="${1}"
  local org_from_api="${2}"
  local org_default="${3}"

  local field_from_api
  field_from_api="$(jq ".${field_name}" <<<"${org_from_api}")"

  if [[ "${field_from_api}" != $(jq ".${field_name}" <<<"${org_default}") ]]; then
    printf "%s: %s," "${field_name}" "${field_from_api}"
  fi
}

if ! bw unlock --check >/dev/null 2>&1; then
  >&2 echo "Error: your bitwarden vault is locked, run 'bw unlock' and follow instructions first!"
  exit 12
fi

ORG_DEFAULT=$(jsonnet -e "(import 'orgs.libsonnet').newOrg('${ORG_GH_NAME}')")
GH_TOKEN=$(bw get item "$(jq -r '.auth.item_id' <<<"${ORG_DEFAULT}")" | jq -r '.fields[]|select(.name=="'"$(jq -r '.auth.admin_api_token' <<<"${ORG_DEFAULT}")"'").value')
export GH_TOKEN

if ! gh auth status >/dev/null 2>&1; then
  gh auth status || :

  >&2 echo "Error: you cannot run this command unauthenticated to GitHub. Check on default org config"
  exit 1
fi

>&2 echo "Info: Logged into Github API as '$(bw get username "$(jq -r '.auth.item_id' <<<"${ORG_DEFAULT}")")'"

ORG_JSON="$(gh api "/orgs/${ORG_GH_NAME}" --cache 3h)"

if ! jq -e '.plan'<<<"${ORG_JSON}" >/dev/null 2>&1; then
  >&2 echo "Error: you cannot run this command on organizations that you're not the owner of!"
  exit 2
fi

mkdir -p "${SCRIPT_FOLDER}/orgs"

{
  cat - <<EOM
    local orgs = import '../orgs.libsonnet';

    orgs.newOrg('${ORG_GH_NAME}') {
      api+: {
EOM

  ORG_DEFAULT_API=$(jq '.api' <<<"${ORG_DEFAULT}")
  for key in $(jq -r 'keys[]' <<<"${ORG_DEFAULT_API}"); do
    valueFromGH="$(jq '.["'"${key}"'"]' <<<"${ORG_JSON}")"
    valueFromDefaultOrg="$(jq '.["'"${key}"'"]' <<<"${ORG_DEFAULT_API}")"

    if [[ "${valueFromGH}" != "${valueFromDefaultOrg}" ]]; then
      printf "%s: %s," "${key}" "${valueFromGH}"
    fi
  done

  echo "},"

  cat - <<EOM
    puppeteer+: {
      $(chmod u+x "${SCRIPT_FOLDER}/build/get_org_infos.js" && "${SCRIPT_FOLDER}/build/get_org_infos.js" -p "puppeteer.jsonnet" <<<"$(jsonnet -e "(import 'orgs.libsonnet').newOrg('${ORG_GH_NAME}')")")
    },
EOM

  ORG_REPOS_JSON="$(gh api "/orgs/${ORG_GH_NAME}/repos" --paginate --cache 3h)"

  echo "repositories+: [ "

  REPOSITORY_DEFAULT_API=$(jq '.repositories[0]' <<<"${ORG_DEFAULT}")
  for repo in $(jq -c '.[]' <<<"${ORG_REPOS_JSON}"); do
    repoName=$(jq -r '.name' <<<"${repo}")
    printedRepo="false"
    for repoKey in $(jq -r 'keys[]|select(. != "name" and . != "branch_protection_rules")' <<<"${REPOSITORY_DEFAULT_API}"); do
      valueFromGH="$(jq '.["'"${repoKey}"'"]' <<<"${repo}")"
      valueFromDefaultOrg="$(jq '.["'"${repoKey}"'"]' <<<"${REPOSITORY_DEFAULT_API}")"
      if [[ "${valueFromGH}" != "${valueFromDefaultOrg}" ]];then
        if [[ "${printedRepo}" == "false" ]]; then
          echo "{"
          printedRepo="true"
        fi
        printf '%s: %s,' "${repoKey}" "${valueFromGH}"
      fi
    done

    # TODO: see TODO-42 below
    if [[ "${printedRepo}" == "false" ]]; then
      echo "{"
      printedRepo="true"
    fi

    REPOSITORY_DEFAULT_BRANCH_PROTECTION=$(jq '.branch_protection_rules[0]' <<<"${REPOSITORY_DEFAULT_API}")
    echo "branch_protection_rules: ["
    for rule in $(gh api graphql --cache 3h --paginate -F repository="${repoName}" -F organization="${ORG_GH_NAME}" -f query="$(<graphql/branchProtectionRules.gql)" | jq -c '.data.repository.branchProtectionRules.nodes[]'); do
      if [[ "$(jq '.pattern' <<<"${REPOSITORY_DEFAULT_BRANCH_PROTECTION}")" != "$(jq '.pattern' <<<"${rule}")" ]]; then
          printf '{%s: %s},' "pattern" "$(jq '.pattern' <<<"${rule}")" || :
          printedRepo="true"
      fi
    done
    printedRepo="true" # TODO-42: only print 'branch_protection_rules[]' when required
    echo "],"

    if [[ "${printedRepo}" == "true" ]]; then
      printf 'name: "%s", },' "${repoName}"
    fi
  done

  echo "],"

  echo "}"
# } > "${SCRIPT_FOLDER}/orgs/${ORG_GH_NAME}.jsonnet"
} | jsonnetfmt --max-blank-lines 1 - > "${SCRIPT_FOLDER}/orgs/${ORG_GH_NAME}.jsonnet"
