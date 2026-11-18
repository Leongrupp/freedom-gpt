"""Create immutable public metadata only after exact-package verification passes."""
import json
import pathlib
import shutil
from datetime import datetime,timezone

from platform_bundle import ROOT,VERSION,sha
from publish_platforms import verify_package_reports,verify_native_macos


def main():
    verify_package_reports(ROOT,VERSION)
    native=verify_native_macos(ROOT,VERSION)
    out=ROOT/'release/platforms'/VERSION
    ubuntu={}
    for kind in ('ubuntu-clean-pc-verification','ubuntu-installers-verification'):
        report=json.loads((ROOT/'logs'/f'{kind}-{VERSION}.json').read_text())
        assert report['passed'] and all(report['checks'].values())
        assert report['workflow']['conclusion']=='success'
        ubuntu[kind]=report
    files={}
    for target in ('windows-x64','ubuntu-x64','macos-arm64'):
        meta=json.loads((out/(target+'.json')).read_text());assert meta['version']==VERSION
        for item in meta['files']:
            p=out/item['name']
            assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
            files[p.name]={**{k:item[k] for k in ('name','bytes','sha256')},
                           'url':f'https://github.com/Leongrupp/freedom-gpt/releases/download/v{VERSION}/{p.name}'}
    windows=json.loads((ROOT/'logs'/f'windows-clean-pc-verification-{VERSION}.json').read_text())
    summary={'version':VERSION,'passed':True,'windows':{'checks':windows['checks'],'environment':windows['environment'],'model_fixture':True},
             'ubuntu':{'checks':{k:v['checks'] for k,v in ubuntu.items()},'workflow':next(iter(ubuntu.values()))['workflow'],'model_fixture':True,'desktop_or_gpu_tested':False},
             'macos':{'checks':native['checks'],'workflow':native['workflow'],'model_fixture':True,'gpu_generation_tested':False,'finder_launch_tested':False},
             'source_alignment':json.loads((ROOT/'logs'/f'source-alignment-verification-{VERSION}.json').read_text()),
             'voice_profiles_included':False,'large_model_weights_included':False}
    proof=out/f'VERIFICATION-{VERSION}.json';proof.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    files[proof.name]={'name':proof.name,'bytes':proof.stat().st_size,'sha256':sha(proof),
                       'url':f'https://github.com/Leongrupp/freedom-gpt/releases/download/v{VERSION}/{proof.name}'}
    manifest={'product':'Freedom GPT','version':VERSION,'public':True,'date':'2026-11-18',
              'platforms':['windows-x64','ubuntu-x64','macos-arm64'],
              'macos_status':'Unsigned Apple Silicon candidate; native core tested with a loopback model fixture; GPU inference not tested',
              'large_model_weights_included':False,'updates_signed':True,'updates_manual_only':True,
              'authenticode_signed':False,'files':list(files.values())}
    (out/'release.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    matrix=json.loads((out/'platforms.json').read_text());matrix['published']=True
    for p in matrix['platforms']:
        for f in p['files']:f['url']=files[f['name']]['url']
    (out/'platforms.json').write_text(json.dumps(matrix,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(out/'platforms.json',ROOT/'site/platforms.json')
    release=json.loads((ROOT/'release/release.json').read_text());release['public']=True
    release['files']=[f for f in files.values() if f['name'].endswith('.exe') or f['name'].endswith('-Windows-x64.zip')]
    (ROOT/'site/release.json').write_text(json.dumps(release,ensure_ascii=False,indent=2),encoding='utf8')
    (out/'SHA256SUMS.txt').write_text(''.join(f['sha256']+'  '+f['name']+'\n' for f in sorted(files.values(),key=lambda f:f['name'])),encoding='ascii')
    shutil.copy2(ROOT/'CROSS-PLATFORM.md',out/'README-BUILDS.md')
    print('VERIFIED_RELEASE_INDEX',VERSION,len(files),flush=True)


if __name__=='__main__':main()
