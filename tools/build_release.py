"""Build custom source archives with the layout expected by the Hub updater."""
import gzip
import hashlib
import os
from pathlib import Path
import sys
import tarfile
import zipfile


def main():
    source = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source))
    from vrhub import __version__, self_install
    version, _ = self_install._source_files(source)
    assert version == __version__
    files = []
    for path in sorted(source.rglob('*')):
        relative = path.relative_to(source)
        if any(p in {'.git','__pycache__','build','dist','.pytest_cache'} or p.endswith('.egg-info') for p in relative.parts):
            continue
        if path.suffix in {'.pyc','.pyo'}:
            continue
        if path.is_symlink():
            raise RuntimeError('Linked source file rejected: '+str(path))
        if path.is_file():
            files.append((path, relative.as_posix()))
    root = 'NAnnersVRhub-'+version
    output = source/'dist';output.mkdir(exist_ok=True)
    archives = []
    for suffix in ('-source.zip','-source.tar.gz'):
        final = output/(root+suffix);pending = output/(root+suffix+'.pending')
        with pending.open('wb') as raw:
            if suffix.endswith('.zip'):
                with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as archive:
                    for path, relative in files:
                        archive.write(path,root+'/'+relative)
            else:
                with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as gz:
                    with tarfile.open(fileobj=gz,mode='w') as archive:
                        for path, relative in files:
                            archive.add(path,arcname=root+'/'+relative,recursive=False)
            raw.flush();os.fsync(raw.fileno())
        os.replace(pending,final)
        archives.append(final)
    with zipfile.ZipFile(archives[0]) as archive:
        assert archive.testzip() is None
        assert archives[0].stat().st_size < 32*1024**2
        assert all(info.file_size <= 8*1024**2 for info in archive.infolist())
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in archives)
    self_install._atomic(output/'SHA256SUMS',sums.encode())
    for path in archives:
        print(str(path)+' ('+str(path.stat().st_size)+' bytes)')


if __name__ == '__main__':
    main()
