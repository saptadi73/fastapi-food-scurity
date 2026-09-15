"""Run Alembic migration with explicit status output.

Use this instead of calling Alembic directly when you want a clear confirmation.
"""
import json
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
ALEMBIC_INI = BACKEND / 'alembic.ini'


def revisions() -> dict:
    config = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(config)
    return {'heads': script.get_heads(), 'bases': script.get_bases()}


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else 'head'
    before = revisions()
    print(json.dumps({'phase': 'before', 'target': target, **before}))
    command = [sys.executable, '-m', 'alembic', '-c', str(ALEMBIC_INI), 'upgrade', target]
    result = subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    after = revisions()
    payload = {'phase': 'after', 'target': target, 'returncode': result.returncode, **after}
    if result.returncode == 0:
        payload['status'] = 'ok'
        print(json.dumps(payload))
        return 0
    payload['status'] = 'failed'
    print(json.dumps(payload))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
