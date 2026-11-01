"""Set public repository metadata: python tools/prepare_repository.py owner/repo"""
import json
import re
import sys
from pathlib import Path
repo = sys.argv[1] if len(sys.argv) == 2 else ''
if not re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', repo):
    raise SystemExit('Usage: python tools/prepare_repository.py owner/repository')
p = Path(__file__).parents[1] / 'custom_components/interphone_live/manifest.json'
data = json.loads(p.read_text())
data.update(documentation=f'https://github.com/{repo}', issue_tracker=f'https://github.com/{repo}/issues', codeowners=['@' + repo.split('/')[0]])
p.write_text(json.dumps(data, indent=2) + '\n')
print('Public repository metadata updated.')
