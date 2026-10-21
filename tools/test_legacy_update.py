"""Exercise the published 0.5.2 updater against a synthetic stable candidate.

Requires a locally verified 0.5.2 source folder and working PySide6. No real
release endpoint is contacted; only mock HTTP transports serve candidate bytes.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-source', type=Path, required=True)
    parser.add_argument('--candidate-source', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    candidate, legacy = args.candidate_source.resolve(), args.legacy_source.resolve()
    sys.path.insert(0, str(candidate))
    from vrhub import self_install, __version__
    version, files = self_install._source_files(candidate)
    assert version == __version__
    for name in ('vrhub/__init__.py', 'pyproject.toml'):
        files[name] = files[name].replace(version.encode(), b'0.5.3')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr('NAnnersVRhub-0.5.3/'+name, data)
    archive = stream.getvalue()
    assert len(archive) < 32*1024**2
    name = 'NAnnersVRhub-0.5.3-source.zip'
    sums = (hashlib.sha256(archive).hexdigest()+'  '+name+'\n').encode()
    metadata = {'id': 530, 'tag_name':'v0.5.3','draft':False,'prerelease':False,
                'html_url':'https://github.com/BananaNanners/NAnnersVRhub/releases/tag/v0.5.3',
                'published_at':'2026-10-21T12:00:00Z','body':'Synthetic migration fixture','assets':[]}
    for asset, content in ((name, archive), ('SHA256SUMS', sums)):
        metadata['assets'].append({'name':asset,'size':len(content),'state':'uploaded',
            'digest':'sha256:'+hashlib.sha256(content).hexdigest(),
            'browser_download_url':'https://github.com/BananaNanners/NAnnersVRhub/releases/download/v0.5.3/'+asset})
    with tempfile.TemporaryDirectory(prefix='hub-legacy-update-') as temporary:
        base = Path(temporary);home = base/'Home with spaces and 100%';home.mkdir()
        state = home/'state/state.json';state.parent.mkdir();state.write_text('{"preserve":"fixture"}\n')
        history = state.parent/'live-tests.json';history.write_text('{"historical":"fixture"}\n')
        save = home/'game-prefix/save.dat';save.parent.mkdir();save.write_bytes(b'preserve external save')
        keep = {p:p.read_bytes() for p in (state,history,save)}
        (base/name).write_bytes(archive);(base/'SHA256SUMS').write_bytes(sums)
        (base/'release.json').write_text(json.dumps(metadata))
        env = {**os.environ,'HOME':str(home),'XDG_DATA_HOME':str(home/'App Data'),
               'XDG_CONFIG_HOME':str(home/'config'),'XDG_CACHE_HOME':str(home/'cache'),
               'VRHUB_STATE':str(state),'QT_QPA_PLATFORM':'offscreen'}
        env.pop('_NANNERSVRHUB_ROOT',None)
        def run(*command):
            result = subprocess.run(list(map(str,command)),cwd=base,env=env,text=True,capture_output=True,timeout=90)
            assert result.returncode==0,result.stdout+result.stderr
            return result.stdout
        run(sys.executable,legacy/'install.py')
        root = home/'App Data/nannersvrhub'
        current = json.loads((root/'installation.json').read_text())['current']
        env['_NANNERSVRHUB_ROOT'] = str(root)
        script = r'''
import io,json,sys
from pathlib import Path
from unittest import mock
sys.path.insert(0,sys.argv[1])
from vrhub import __version__,app_updates
assert __version__=='0.5.2'
assert app_updates.MAX_ARCHIVE==32*1024**2
assert app_updates.MAX_FILE==8*1024**2
base=Path(sys.argv[2]);metadata=json.loads((base/'release.json').read_text())
class Response(io.BytesIO):
 status=200
 def __init__(self,data,url):
  super().__init__(data);self.url=url;self.headers={'Content-Length':str(len(data))}
 def geturl(self):return self.url
def response(url):
 data=json.dumps(metadata).encode() if url==app_updates.API else (base/url.rsplit('/',1)[-1]).read_bytes()
 return Response(data,url)
with mock.patch.object(app_updates,'_open',side_effect=response):
 release=app_updates.check(force=True)['release']
 bundle=app_updates.download(release)
 installed=app_updates.install_bundle(Path(bundle['directory']))
 assert installed['version']=='0.5.3',installed
print('Published 0.5.2 updater: check/download/verify/install passed')
'''
        print(run(sys.executable,'-I','-B','-c',script,root/'releases'/current,base).strip())
        assert '0.5.3' in run(root/'bin/nannersvrhub','--version')
        new = json.loads((root/'installation.json').read_text())['current']
        check = "import sys;sys.path.insert(0,sys.argv[1]);from vrhub import hub,kharvox_bridge;assert len(hub.load_recipes())==9;assert not kharvox_bridge.rows()[0]['ok'];print('Nine profiles load without optional component')"
        print(run(sys.executable,'-I','-c',check,root/'releases'/new).strip())
        run(root/'bin/nannersvrhub-manage','rollback')
        assert '0.5.2' in run(root/'bin/nannersvrhub','--version')
        run(root/'bin/nannersvrhub-manage','rollback')
        assert '0.5.3' in run(root/'bin/nannersvrhub','--version')
        for path, content in keep.items():assert path.read_bytes()==content,path
        print('PASS: legacy limits/resource policy, managed restart, two-way rollback, state/history/save preservation')


if __name__=='__main__':
    main()
