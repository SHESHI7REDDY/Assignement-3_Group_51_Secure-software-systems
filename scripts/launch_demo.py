"""Standard-library bootstrap for the local, isolated coursework demo."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info < (3, 12):
        raise RuntimeError('Install Python 3.12 or newer from python.org first.')
    environment = ROOT / '.venv-demo'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('First launch: creating the project Python environment.', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    requirements = ROOT / 'requirements.txt'
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / 'installed-requirements.sha256'
    if not marker.exists() or marker.read_text() != digest:
        print('Installing project dependencies. First launch needs internet access.', flush=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True, cwd=ROOT)
        marker.write_text(digest)
    subprocess.run([str(python), '-m', 'scripts.demo_runtime', *sys.argv[1:]], cwd=ROOT, check=True)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nDemo stopped.')
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f'Could not start the demo: {error}', file=sys.stderr)
        raise SystemExit(1)
