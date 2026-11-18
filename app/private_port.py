"""Recover only an OS-denied private model port; keep loopback isolation."""
import socket
import time
import shutil

def migrate_urls(old,new):
    import bootstrap as b
    import hermes_yaml as yaml
    from hermes_cli.config import atomic_config_write
    path=b.HOME/'config.yaml';cfg=yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    changed=False
    def visit(value):
        nonlocal changed
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='base_url' and item==old:value[key]=new;changed=True
                else:visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(cfg)
    if changed:atomic_config_write(path,cfg)

def denied(port):
    with socket.socket() as sock:
        try:sock.bind(('127.0.0.1',port))
        except OSError as exc:return getattr(exc,'winerror',None)==10013
    return False

def repair():
    import bootstrap as b
    if not b.PRIVATE:return None
    # Finish an interrupted route migration before starting the panel again.
    for source,target in b.read(b.ROOT/'data/model-port-migrations.json',{}).items():
        if target==b.model_url():migrate_urls(source,target)
    cfg=b.config();old=cfg['model_port']
    if not denied(old):return None
    # A Windows/Hyper-V exclusion denies bind without a listener. Never stop
    # another application or remove OS-wide port reservations.
    selected=None
    for port in range(19135,19235):
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port));selected=port;break
            except OSError:continue
    if selected is None:raise RuntimeError('Нет доступного порта для локальной модели.')
    folder=b.ROOT/'archive'/('port-repair-'+str(time.time_ns()));folder.mkdir(parents=True)
    for file in (b.ROOT/'data/settings.json',b.STACK/'server-settings.json',b.HOME/'config.yaml'):
        shutil.copy2(file,folder/file.name)
    from managed_models import stop
    stop()
    engine=b.read(b.STACK/'server-settings.json',{});engine['port']=selected
    cfg['model_port']=selected
    if cfg.get('external_url')==f'http://127.0.0.1:{old}/v1':cfg['external_url']=f'http://127.0.0.1:{selected}/v1'
    b.write(b.STACK/'server-settings.json',engine);b.write(b.ROOT/'data/settings.json',cfg)
    migrations=b.read(b.ROOT/'data/model-port-migrations.json',{})
    old_url=f'http://127.0.0.1:{old}/v1';new_url=f'http://127.0.0.1:{selected}/v1'
    migrations={source:new_url if target==old_url else target for source,target in migrations.items()}
    migrations[old_url]=new_url
    b.write(b.ROOT/'data/model-port-migrations.json',migrations)
    migrate_urls(f'http://127.0.0.1:{old}/v1',f'http://127.0.0.1:{selected}/v1')
    b.write_hermes()
    return {'old_port':old,'new_port':selected,'backup':str(folder)}
