#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
python3 - "$ROOT" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
roles = json.loads((root / 'config/delivery-roles.json').read_text())['roles']
required = {
    'author': {'design:impeccable', 'design:better-writing', 'design:apple-design'},
    'reviewer': {'design:interface-review', 'design:review-animations', 'design:better-interface',
                 'design:better-accessibility', 'design:better-layout', 'design:better-writing',
                 'design:better-typography', 'design:better-colors', 'design:better-ui'},
    'evaluator': {'design:better-interface', 'design:better-accessibility', 'design:better-layout',
                  'design:better-writing', 'design:better-typography', 'design:better-colors',
                  'design:better-ui'},
}
for role, expected in required.items():
    actual = set(roles[role]['skills'])
    missing = expected - actual
    assert not missing, f'{role} misses {sorted(missing)}'
assert all('design:variant' not in set(entry['skills']) for entry in roles.values())
PY
"$ROOT/bin/role-adoption-trial" verify-distribution
