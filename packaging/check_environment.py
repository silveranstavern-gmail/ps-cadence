"""Refuse to create a release with silently changed Python dependencies."""
import argparse
from importlib.metadata import version
from pathlib import Path
import platform
import site
import sys

from packaging.requirements import Requirement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cpu', action='store_true')
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.machine().upper() in ('AMD64', 'X86_64'), 'Build on Windows x64.'
    assert sys.version_info[:2] == (3, 11), 'This release is validated with Python 3.11.'
    assert sys.prefix != sys.base_prefix
    assert not any(Path(p).is_relative_to(sys.base_prefix) for p in site.getsitepackages()), 'Do not inherit global packages.'
    lock = Path(__file__).resolve().parents[1] / ('requirements-cpu.lock.txt' if args.cpu else 'requirements-nvidia.lock.txt')
    for line in lock.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith(('#', '--')):
            continue
        req = Requirement(line)
        installed = version(req.name)
        if req.url:
            assert req.name.replace('-', '_') == 'en_core_web_sm' and installed == '3.8.0'
        else:
            assert installed in req.specifier, f'{req.name}: installed {installed}, expected {req.specifier}'
    print('Release environment matches the dependency lock.')


if __name__ == '__main__':
    main()
