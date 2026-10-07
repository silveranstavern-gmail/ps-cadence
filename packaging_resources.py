"""Supplement dynamic phonemizer resources missed by automatic bundler hooks."""
from pathlib import Path
import shutil

from PyInstaller.utils.hooks import collect_data_files


def main():
    root = Path(__file__).resolve().parent
    bundle = (root / 'dist' / 'Cadence' / '_internal').resolve()
    if not bundle.is_relative_to(root) or not bundle.is_dir():
        raise RuntimeError('Build the executable inside this project before copying its resources.')
    for package in ['language_tags', 'csvw', 'segments', 'phonemizer', 'num2words']:
        for source, destination in collect_data_files(package):
            folder = (bundle / destination).resolve()
            if not folder.is_relative_to(bundle):
                raise RuntimeError('Resource target escaped the bundle.')
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, folder / Path(source).name)
    print('Phonemizer resource files included.')
    shutil.copytree(root / 'vendor' / 'webview2', bundle / 'webview2', dirs_exist_ok=True)
    print('Fixed WebView2 runtime included.')


if __name__ == '__main__':
    main()
