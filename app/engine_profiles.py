"""Reuse measured local engine settings for the same model, device and context."""
import pathlib
import time

from bootstrap import ROOT, read, write

PATH = ROOT / 'data/model-context-profiles.json'
FIELDS = ('ngl', 'kv_cache', 'mtp', 'draft_tokens', 'threads', 'threads_batch',
          'batch_size', 'ubatch_size', 'priority', 'cpu_poll', 'performance_mode',
          'performance_key', 'fit_margin_mb')


def device_key(cfg):
    hardware = read(ROOT / 'data/hardware.json', {})
    return [cfg.get('backend'), hardware.get('ram_gb'),
            [[g.get('name'), g.get('vram_gb')] for g in hardware.get('gpus', [])]]


def model_stamp(cfg):
    value = pathlib.Path(cfg['model']).stat()
    return [value.st_size, value.st_mtime_ns]


def load(cfg):
    entry = read(PATH, {}).get(cfg.get('catalog_id'), {})
    profile = entry.get('profiles', {}).get(str(cfg['context']), {})
    if (profile.get('device') != device_key(cfg)
            or profile.get('model_stat') != model_stamp(cfg)):
        return {}
    values = {key: profile['engine'][key] for key in FIELDS if key in profile.get('engine', {})}
    if values:
        values.update(context_mode='selected', context_verified=True, fit_min_context=cfg['context'])
    return values


def remember(cfg, measurement):
    if cfg.get('performance_mode') != 'turbo':
        return
    entries = read(PATH, {})
    entry = entries.setdefault(cfg['catalog_id'], {})
    entry.update(device=device_key(cfg), context=cfg['context'], ngl=cfg['ngl'])
    entry.setdefault('profiles', {})[str(cfg['context'])] = {
        'device': device_key(cfg), 'model_stat': model_stamp(cfg),
        'engine': {key: cfg[key] for key in FIELDS if key in cfg},
        'measurement': measurement, 'updated': time.time(),
    }
    write(PATH, entries)
