#!/bin/bash

# if gh is not installed, raise an error
if ! command -v gh >/dev/null 2>&1
then
    echo "gh could not be found"
    echo "Please install gh, e.g. 'brew install gh'"
    exit 1
fi

SUBMODULE_BRANCH="vocodehq-public"

USER=$(gh api user | jq -r '.login')
DATE=$(date +%Y%m%d%H%M%S)
PR_TITLE="Update ${SUBMODULE_BRANCH}"
PR_BODY="This PR updates the ${SUBMODULE_BRANCH} branch by merging changes from the main branch."

echo "Creating a new branch ${FEATURE_BRANCH}"

git checkout ${SUBMODULE_BRANCH}
git pull origin ${SUBMODULE_BRANCH}
git checkout main
git pull origin main
gh pr create -t "${PR_TITLE}" -b "${PR_BODY}" -B ${SUBMODULE_BRANCH}
