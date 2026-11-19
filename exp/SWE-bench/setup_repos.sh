#!/usr/bin/env bash
# Clone the 12 SWE-bench repositories (mirrors kept by the SWE-bench team) into $MAGIS_REPO_PATH.
# Uses HTTPS so no GitHub SSH key is needed.
set -e
REPO_PATH="${MAGIS_REPO_PATH:-$HOME/SWE-bench-repo}"
mkdir -p "$REPO_PATH"
cd "$REPO_PATH"
for repo in astropy__astropy django__django matplotlib__matplotlib mwaskom__seaborn pallets__flask \
            psf__requests pydata__xarray pylint-dev__pylint pytest-dev__pytest scikit-learn__scikit-learn \
            sphinx-doc__sphinx sympy__sympy; do
    if [ -d "$repo" ]; then
        echo "$repo exists"
    else
        git clone "https://github.com/swe-bench/$repo.git"
    fi
done
