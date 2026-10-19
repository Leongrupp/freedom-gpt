"""Relocatable console entry points for the private Python distribution."""
import importlib,json,pathlib,sys
table=json.loads((pathlib.Path(__file__).resolve().parent/'freedom-entrypoints.json').read_text())
name=sys.argv.pop(1);module,attribute=table[name].split(':',1);value=importlib.import_module(module)
for part in attribute.split('.'):
 if part:value=getattr(value,part)
raise SystemExit(value())
