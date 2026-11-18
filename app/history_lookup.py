"""Read-only, offline recall for Freedom's saved display history."""
import argparse,contextlib,json,pathlib,re,sqlite3,sys

def stems(text):
    words=re.findall(r'[\w]+',(text or '').casefold())
    stop={'как','что','это','для','или','мне','меня','его','она','они','оно','был','было','быть','про','при','наш','наша','нужно','надо','этот','этого','этом','the','and','with'}
    result=[]
    for word in words:
        if word in stop or len(word)<3:continue
        if re.search('[а-яё]',word) and len(word)>4:
            shortened=re.sub(r'(иями|ами|ями|ого|ему|ому|ыми|ими|ая|яя|ый|ий|ой|ое|ее|ые|ие|ую|юю|ия|ию|ть|ов|ев|ах|ях|ам|ям|ом|ем|у|ю|а|я|ы|и|е|о)$','',word)
            if len(shortened)>=3:word=shortened
        result.append(word)
    return set(result)

def recall_score(text,query):
    text=(text or '').casefold();query=(query or '').strip().casefold()
    if not query:return 1
    exact=1000 if query in text else 0
    terms=stems(query);found=len(terms&stems(text))
    return exact+found*20+(100 if terms and found==len(terms) else 0)

def visible_text(content):
    if isinstance(content,str):return content
    if isinstance(content,list):return '\n'.join(str(item.get('text','')) for item in content if isinstance(item,dict) and item.get('type')=='text')
    return ''

def lookup(path,session,query='',uid=None,offset=0,chars=12000,limit=5,tools=False):
    if not pathlib.Path(path).is_file():return {'messages':[],'note':'Архив ещё не создан. Используй native session_search.'}
    with contextlib.closing(sqlite3.connect('file:'+pathlib.Path(path).as_posix()+'?mode=ro',uri=True,timeout=3)) as c:
        c.row_factory=sqlite3.Row;c.create_function('recall_score',2,recall_score)
        c.create_function('has_text',1,lambda body:bool(visible_text(json.loads(body).get('content')).strip()))
        if uid:rows=c.execute('SELECT * FROM history_messages WHERE sid=? AND uid=?',(session,uid)).fetchall()
        else:
            visible='' if tools else " AND role<>'tool' AND has_text(body)"
            rows=c.execute('SELECT *,recall_score(search_text,?) AS relevance FROM history_messages WHERE sid=? AND recall_score(search_text,?)>0'+visible+' ORDER BY relevance DESC,seq DESC LIMIT ?',(query,session,query,max(1,min(20,limit)))).fetchall()
    result=[];budget=max(1000,min(24000,chars))
    for row in rows:
        message=json.loads(row['body']);content=message.get('content','')
        if not isinstance(content,str):content=visible_text(content)
        if message.get('tool_calls'):content+='\n'+json.dumps(message['tool_calls'],ensure_ascii=False)
        start=max(0,offset) if uid else 0
        if not uid and query:
            pos=content.casefold().find(query.casefold());start=max(0,pos-300)
        part=content[start:start+budget];budget-=len(part)
        result.append({'uid':row['uid'],'role':row['role'],'timestamp':row['stamp'],'content':part,'offset':start,'next_offset':start+len(part) if start+len(part)<len(content) else None,'total_chars':len(content)})
        if budget<=0:break
    return {'session':session,'messages':result,'note':'Сохранённая история, а не подтверждение текущего состояния файлов. Для продолжения длинной записи используй uid и next_offset.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--session',required=True);parser.add_argument('--query',default='');parser.add_argument('--uid');parser.add_argument('--offset',type=int,default=0);parser.add_argument('--chars',type=int,default=12000);parser.add_argument('--limit',type=int,default=5);parser.add_argument('--tools',action='store_true',help='Include saved tool arguments/results')
    args=parser.parse_args();path=pathlib.Path(__file__).resolve().parent/'data/chat-history.sqlite'
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(lookup(path,args.session,args.query,args.uid,args.offset,args.chars,args.limit,args.tools),ensure_ascii=False))
