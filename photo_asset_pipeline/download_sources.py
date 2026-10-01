"""Restore audited originals from recorded URLs; never overwrite differing files.

Requires requests. Ordinary builds need no network. The downloaded bytes must
match the recorded SHA-256; a changed remote image needs another source review.
"""
from pathlib import Path
import hashlib,io,json,zipfile
import requests

ROOT=Path(__file__).resolve().parent


def main():
    selected={s for a in json.loads((ROOT/'manifest.json').read_text())['assets'].values() for s in a['sources']}
    for name in sorted(selected):
        metadata=json.loads((ROOT/'sources'/name/'source.json').read_text(encoding='utf8'))
        path=ROOT/metadata['original_file']
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata['sha256']:raise ValueError(f'Modified original: {path}')
            print(name+': original verified');continue
        response=requests.get(metadata['direct_image_url'],timeout=90,headers={'User-Agent':'PhotoAssetStudy/1.0'})
        response.raise_for_status();data=response.content
        if 'archive_sha256' in metadata:
            if hashlib.sha256(data).hexdigest()!=metadata['archive_sha256']:raise ValueError('Changed archive: '+name)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:data=archive.read(path.name)
        if hashlib.sha256(data).hexdigest()!=metadata['sha256']:raise ValueError('Changed image: '+name)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);print(name+': restored')


if __name__=='__main__':main()
