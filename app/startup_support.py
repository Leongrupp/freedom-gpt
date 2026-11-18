"""Process-local startup safeguards; no Windows proxy or model settings changes."""
import logging,os,urllib.request


def install_bundled_features(root,home):
    """Install trusted app plugins before the first gateway starts; preserve skills."""
    import json,pathlib,shutil
    root,home=pathlib.Path(root),pathlib.Path(home)
    source=root/'runtime/freedom'
    for name in ('freedom-accounts','freedom-preview','freedom-progress','freedom-team'):
        plugin=source/'agent_plugins'/name
        if not plugin.is_dir():continue
        target=home/'plugins'/name
        shutil.copytree(plugin,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('runtime.json','__pycache__','*.pyc'))
        (target/'runtime.json').write_text(json.dumps({'app_relative':os.path.relpath(root,target)}),encoding='utf8')
    skill=source/'builtin_skills/arshi';target=home/'skills/arshi'
    if skill.is_dir() and not target.exists():shutil.copytree(skill,target)

def configure_local_proxy(environ=None,proxies=None):
    env=os.environ if environ is None else environ
    # Capture existing system proxies before NO_PROXY makes urllib prefer the
    # environment over the Windows registry. Keep external requests on them.
    discovered=urllib.request.getproxies() if proxies is None else proxies
    if os.name=='nt' or proxies is not None:
        for scheme in ('http','https','ftp','all'):
            if discovered.get(scheme) and not any(k.lower()==scheme+'_proxy' for k in env):
                env[scheme.upper()+'_PROXY']=discovered[scheme]
    values=[env.get('NO_PROXY',''),env.get('no_proxy',''),discovered.get('no','')]
    if os.name=='nt' and environ is None:
        # Preserve explicit Windows bypass entries alongside loopback entries.
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                override=winreg.QueryValueEx(key,'ProxyOverride')[0]
            values.append(str(override).replace(';',','))
        except OSError:pass
    entries=list(dict.fromkeys(x.strip() for value in values for x in value.split(',') if x.strip()))
    for host in ('127.0.0.1','localhost','::1','[::1]'):
        if host not in entries:entries.append(host)
    env['NO_PROXY']=env['no_proxy']=','.join(entries)

def activate_saved_model(library,ident):
    try:
        library.activate(ident)
        return True
    except (ValueError,OSError) as error:
        library.activation={'id':ident,'state':'error','error':str(error)}
        logging.getLogger('freedom.startup').warning('Local model activation deferred: %s',error)
        return False
