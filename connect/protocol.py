"""Small, versioned wire protocol shared with the portable PC client."""
import base64,hashlib,re,urllib.parse
VERSION=1
CHUNK=48*1024
MAX_UPLOAD=20*1024*1024
MAX_DOWNLOAD=512*1024*1024
MAX_FRAME=2*1024*1024

def encode(raw):return base64.b64encode(raw).decode('ascii')
def decode(text,limit=CHUNK):
    if not isinstance(text,str) or len(text)>limit*2:raise ValueError('Invalid frame length')
    raw=base64.b64decode(text,validate=True)
    if len(raw)>limit:raise ValueError('Frame too large')
    return raw
def client_id(public):
    if len(public)!=32:raise ValueError('Invalid public key')
    return hashlib.sha256(public).hexdigest()[:32]
def signed_challenge(nonce,origin):
    return ('Freedom GPT phone relay v1\n'+origin+'\n'+nonce).encode()
def api_path(raw):
    if not isinstance(raw,str) or len(raw)>8192 or any(ord(c)<32 for c in raw):raise ValueError('Invalid API path')
    parsed=urllib.parse.urlsplit(raw)
    if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith('/api/'):raise ValueError('Only local API requests are allowed')
    path=parsed.path
    for _ in range(3):path=urllib.parse.unquote(path)
    if '\\' in path or any(part in {'.','..'} for part in path.split('/')):raise ValueError('Invalid path')
    if path.startswith(('/api/phone','/api/remote-control')):raise ValueError('Phone controls are PC-only')
    return raw
def request_headers(value):
    allowed={'content-type','x-freedom-token','range','if-range','if-none-match','if-modified-since','accept'}
    if not isinstance(value,dict) or len(value)>40:raise ValueError('Invalid headers')
    result={}
    for k,v in value.items():
        if k.lower() in allowed and isinstance(v,str) and len(v)<8192 and not any(c in v for c in '\r\n'):
            result[k]=v
    return result
def response_headers(value,path):
    if not isinstance(value,dict):raise ValueError('Invalid headers')
    allowed={'content-type','content-disposition','content-range','accept-ranges','etag','last-modified'}
    result={k:v for k,v in value.items() if k.lower() in allowed and isinstance(v,str) and len(v)<8192 and not any(c in v for c in '\r\n')}
    kind=next((v.split(';')[0].lower() for k,v in result.items() if k.lower()=='content-type'),'application/octet-stream')
    media={'image/png','image/jpeg','image/webp','image/gif','image/bmp','video/mp4','video/webm','video/quicktime','audio/mpeg','audio/wav'}
    if kind not in media and kind!='application/json':
        result={k:v for k,v in result.items() if k.lower() not in {'content-type','content-disposition'}}
        result.update({'Content-Type':'application/octet-stream','Content-Disposition':'attachment'})
    return result
