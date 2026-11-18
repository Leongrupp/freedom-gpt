import pathlib,runpy,threading,time,json
root=pathlib.Path('/work')
threading.Thread(target=lambda:runpy.run_path(str(root/'packaging/qa/model_fixture.py'),run_name='__main__'),daemon=True).start()
time.sleep(.3)
runpy.run_path(str(root/'packaging/qa/ubuntu_portable.py'),run_name='__main__')
runpy.run_path(str(root/'packaging/qa/ubuntu_installers.py'),run_name='__main__')
report={k:json.loads((root/'logs'/k).read_text()) for k in ['ubuntu-clean-pc-verification-1.7.0.json','ubuntu-installers-verification-1.7.0.json']}
print('FREEDOM_UBUNTU_RESULT='+json.dumps(report),flush=True)
