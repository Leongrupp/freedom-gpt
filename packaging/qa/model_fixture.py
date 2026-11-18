import json,time,pathlib,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  raw=json.dumps({'status':'ok','data':[{'id':'freedom-test','object':'model'}]}).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))));time.sleep(9)
  text='QA response complete.'
  self.send_response(200)
  if data.get('stream'):
   self.send_header('Content-Type','text/event-stream');self.send_header('Connection','close');self.end_headers()
   for chunk in [{'choices':[{'index':0,'delta':{'role':'assistant','content':text},'finish_reason':None}]},{'choices':[{'index':0,'delta':{},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':4,'total_tokens':24}}]:self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode());self.wfile.flush()
   self.wfile.write(b'data: [DONE]\n\n');self.close_connection=True
  else:
   raw=json.dumps({'id':'qa','object':'chat.completion','choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':4,'total_tokens':24}}).encode();self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
ThreadingHTTPServer(('127.0.0.1',19179),Handler).serve_forever()
