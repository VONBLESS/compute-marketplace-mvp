from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    # Placeholder worker entrypoint for containerized execution.
    payload = {'argv': sys.argv[1:]}
    print(json.dumps({'status': 'ok', 'payload': payload}))
    return subprocess.call(sys.argv[1:]) if len(sys.argv) > 1 else 0


if __name__ == '__main__':
    raise SystemExit(main())
