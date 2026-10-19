"""Stop this installation's owned background services before unplugging its SSD."""
import bootstrap
import json,pathlib,time,psutil
from bootstrap import ROOT,STACK,read
from library import library
if not bootstrap.PRIVATE:library.stop_model()
record=read(ROOT/'.tmp/server-process.json',{})
try:
 process=psutil.Process(record['pid'])
 if abs(process.create_time()-record['created'])<1 and str(ROOT/'server.py').lower() in ' '.join(process.cmdline()).lower():process.terminate();process.wait(timeout=15)
except (KeyError,psutil.NoSuchProcess):pass
from hermes_cli.gateway import stop_profile_gateway
stop_profile_gateway()
print('Freedom GPT background services stopped. Close its browser window and safely eject the disk in Windows.')
