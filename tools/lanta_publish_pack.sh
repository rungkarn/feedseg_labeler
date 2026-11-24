#!/bin/bash
# Run ON LANTA (transfer node `lanta`, which can reach github.com). Images never touch the local PC.
#
#   bash tools/lanta_publish_pack.sh [export_pellet_pack.py args, e.g. --task gold_asian_2_0019,gold_asian_2S_0030 --replace]
#   no --task = all 55 tasks (~0.3 GB: push in a few batches if GitHub complains)
#
# Two clones on Lanta (each with its own read-write deploy key; GitHub allows one repo per key):
#   $FL_CODE  = feedseg_labeler        (code;   ssh alias github-fl  ) - only pulled here
#   $FL_PACKS = feedseg_labeler_packs  (images; ssh alias github-flp ) - pushed here
# The site (docs/config.json "packsBase") reads images from https://rungkarn.github.io/feedseg_labeler_packs/.
set -euo pipefail
CODE=${FL_CODE:-/project/lt200264-saiwat/FeedProject/web/feedseg_labeler_repo}
PACKS=${FL_PACKS:-/project/lt200264-saiwat/FeedProject/web/feedseg_labeler_packs_repo}
PY=${FL_PY:-/project/lt200264-saiwat/Env/segmentation/bin/python}

git -C "$CODE" pull -q --ff-only
git -C "$PACKS" pull -q --ff-only
"$PY" -I "$CODE/tools/export_pellet_pack.py" --site "$PACKS" "$@"   # writes $PACKS/packs/<task>/ + packs/index.json
cd "$PACKS"
git add packs
if git diff --cached --quiet; then echo "nothing to commit"; exit 0; fi
git commit -q -m "packs: $* (exported on Lanta)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
git push -q origin main
git log -1 --oneline
echo "pushed. live in ~1 min: https://rungkarn.github.io/feedseg_labeler/"
