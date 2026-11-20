"""Shared CI version checks and Windows artifact staging (Python 3.11+)."""
import argparse
import os
from pathlib import Path
import re
import shutil
import tomllib


def project_version(tag=None):
    version = tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[a-zA-Z0-9.+-]*)', version):
        raise ValueError(f'Unsafe or unsupported release version: {version!r}')
    if tag is not None and tag != f'v{version}':
        raise ValueError(f'Tag {tag!r} does not match project version v{version}')
    return version


def require_file(path):
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f'Missing or empty release artifact: {path}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['version', 'windows', 'verify'])
    args = parser.parse_args()
    tag = os.environ.get('GITHUB_REF_NAME') if os.environ.get('GITHUB_REF_TYPE') == 'tag' else None
    version = project_version(tag)
    if args.command == 'version':
        print(version)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
                output.write(f'version={version}\n')
    elif args.command == 'windows':
        source = Path('dist/OpenStatement.exe')
        require_file(source)
        if source.read_bytes()[:2] != b'MZ':
            raise ValueError('Windows output is not a PE executable')
        target = Path(f'dist/packages/OpenStatement-{version}-Windows-x64.exe')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    else:
        for name in (f'OpenStatement-{version}-Windows-x64.exe',
                     f'openstatement_{version}_amd64.deb',
                     f'OpenStatement-{version}-x86_64.AppImage'):
            require_file(Path('dist/packages') / name)


if __name__ == '__main__':
    main()
