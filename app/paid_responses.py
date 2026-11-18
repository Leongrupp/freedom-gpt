"""Responses transport for paid OpenAI/xAI, presented to the existing chat gateway."""
import asyncio,contextlib,json,time,uuid
from aiohttp import ClientSession,ClientTimeout,ClientError,web
from cloud_catalog import PROVIDERS

class ResponsesAdapter:
    def __init__(self,owner):
        self.owner=owner
        with owner.db() as db:db.execute('CREATE TABLE IF NOT EXISTS cloud_response_state(provider TEXT,model TEXT,call_id TEXT,items TEXT,created REAL,PRIMARY KEY(provider,model,call_id))')

    def input(self,target,messages):
        result=[];restored=set()
        for message in messages:
            role=message.get('role')
            if role=='tool':
                result.append({'type':'function_call_output','call_id':message.get('tool_call_id',''),
                               'output':str(message.get('content') or '')});continue
            content=message.get('content')
            calls=message.get('tool_calls') or []
            if role=='assistant' and calls:
                for call in calls:
                    with self.owner.db() as db:
                        row=db.execute('SELECT items FROM cloud_response_state WHERE provider=? AND model=? AND call_id=?',
                            (target['provider_id'],target['remote_id'],call['id'])).fetchone()
                    if row:
                        for item in json.loads(row[0]):
                            identity=item.get('id') or json.dumps(item,sort_keys=True)
                            if identity not in restored:result.append(item);restored.add(identity)
            if content:
                if isinstance(content,str):parts=[{'type':'output_text' if role=='assistant' else 'input_text','text':content}]
                else:
                    parts=[]
                    for part in content:
                        if part.get('type')=='text':parts.append({'type':'output_text' if role=='assistant' else 'input_text','text':part.get('text','')})
                        elif part.get('type')=='image_url' and role=='user':
                            image=part.get('image_url') or {};parts.append({'type':'input_image','image_url':image.get('url',''),**({'detail':image['detail']} if image.get('detail') else {})})
                if parts:result.append({'role':role,'content':parts})
            for call in calls:
                function=call.get('function') or {}
                result.append({'type':'function_call','call_id':call['id'],'name':function.get('name',''),'arguments':function.get('arguments') or '{}'})
        return result

    def body(self,target,body):
        effort=body.get('reasoning_effort') or 'low'
        if effort in {'none','minimal'} and (target['provider_id']=='xai' or target['remote_id']!='gpt-6-luna'):effort='low'
        result={'model':target['remote_id'],'input':self.input(target,body.get('messages',[])),
                'store':False,'include':['reasoning.encrypted_content'],'max_output_tokens':body['max_tokens'],
                'reasoning':{'effort':effort},'stream':bool(body.get('stream'))}
        if body.get('tools'):
            result['tools']=[{'type':'function',**{k:v for k,v in tool['function'].items() if k in {'name','description','parameters'}},'strict':False}
                             for tool in body['tools'] if tool.get('type')=='function']
        if body.get('tool_choice'):
            choice=body['tool_choice']
            result['tool_choice']={'type':'function','name':choice['function']['name']} if isinstance(choice,dict) else choice
        if body.get('parallel_tool_calls') is not None:result['parallel_tool_calls']=body['parallel_tool_calls']
        if body.get('response_format'):
            fmt=body['response_format']
            result['text']={'format':{'type':'json_schema',**fmt['json_schema']} if fmt.get('type')=='json_schema' else fmt}
        if target['provider_id']=='xai' or effort=='none':
            for key in ('temperature','top_p'):
                if body.get(key) is not None:result[key]=body[key]
        return result

    def remember(self,target,response):
        reasoning=[item for item in response.get('output',[]) if item.get('type')=='reasoning']
        raw=json.dumps(reasoning,ensure_ascii=False)
        if not reasoning or len(raw)>256000:return
        with self.owner.db() as db:
            for item in response.get('output',[]):
                if item.get('type')=='function_call':
                    db.execute('INSERT OR REPLACE INTO cloud_response_state VALUES(?,?,?,?,?)',
                        (target['provider_id'],target['remote_id'],item['call_id'],raw,time.time()))
            db.execute('DELETE FROM cloud_response_state WHERE created<?',(time.time()-30*86400,))
            db.execute('DELETE FROM cloud_response_state WHERE rowid IN (SELECT rowid FROM cloud_response_state ORDER BY created DESC LIMIT -1 OFFSET 256)')

    @staticmethod
    def usage(response):
        usage=response.get('usage') or {}
        return {'prompt_tokens':usage.get('input_tokens',0),'completion_tokens':usage.get('output_tokens',0),
                'total_tokens':usage.get('total_tokens',0),
                'prompt_tokens_details':usage.get('input_tokens_details') or {},'completion_tokens_details':usage.get('output_tokens_details') or {}}

    def result(self,target,response):
        self.remember(target,response)
        content=''.join(part.get('refusal','') if part.get('type')=='refusal' else part.get('text','')
                        for item in response.get('output',[]) if item.get('type')=='message'
                        for part in item.get('content',[]) if part.get('type') in {'output_text','text','refusal'})
        calls=[{'id':item['call_id'],'type':'function','function':{'name':item['name'],'arguments':item.get('arguments') or '{}'}}
               for item in response.get('output',[]) if item.get('type')=='function_call']
        finish='tool_calls' if calls else 'length' if response.get('status')=='incomplete' else 'stop'
        return {'id':response.get('id') or 'chatcmpl-'+uuid.uuid4().hex,'object':'chat.completion','created':int(time.time()),
                'model':target['remote_id'],'choices':[{'index':0,'message':{'role':'assistant','content':content or None,**({'tool_calls':calls} if calls else {})},'finish_reason':finish}],
                'usage':self.usage(response)}

    async def chat(self,request,target,body,credential):
        started=time.monotonic();first=None;tokens=0;response=None;failure=None
        try:
            async with ClientSession(timeout=ClientTimeout(total=900,connect=15,sock_read=180),read_bufsize=1024*1024) as http:
                async with http.post(PROVIDERS[target['provider_id']]['base']+'/responses',json=self.body(target,body),
                    headers={'Authorization':'Bearer '+credential['key'],'Content-Type':'application/json'},allow_redirects=False) as upstream:
                    if upstream.status!=200:
                        failure={'status':upstream.status}
                        return web.json_response({'error':{'message':self.owner.upstream_error(upstream.status,True),'type':'upstream_error'}},
                            status=upstream.status if upstream.status in {400,401,402,403,413,422,429} else 400)
                    if not body.get('stream'):
                        value=await upstream.json()
                        if value.get('status')=='failed':raise ValueError('Платный API не завершил ответ. Автоматического повтора нет.')
                        result=self.result(target,value);tokens=result['usage']['completion_tokens'];return web.json_response(result)
                    response=web.StreamResponse(status=200,headers={'Content-Type':'text/event-stream','Cache-Control':'no-store'})
                    await response.prepare(request)
                    identity='chatcmpl-'+uuid.uuid4().hex;indexes={};arguments=set();terminal=False
                    async def emit(delta,finish=None,usage=None):
                        nonlocal first
                        if first is None and (delta.get('content') or delta.get('tool_calls')):first=time.monotonic()
                        chunk={'id':identity,'object':'chat.completion.chunk','created':int(time.time()),'model':target['remote_id'],
                            'choices':[{'index':0,'delta':delta,'finish_reason':finish}] if usage is None else [],**({'usage':usage} if usage is not None else {})}
                        await response.write(('data: '+json.dumps(chunk,ensure_ascii=False)+'\n\n').encode())
                    await emit({'role':'assistant'})
                    async for line in upstream.content:
                        if not line.startswith(b'data:'):continue
                        try:event=json.loads(line[5:].strip())
                        except ValueError:continue
                        kind=event.get('type','')
                        if kind in {'response.output_text.delta','response.refusal.delta'}:await emit({'content':event.get('delta','')})
                        elif kind=='response.output_item.added' and event.get('item',{}).get('type')=='function_call':
                            item=event['item'];index=len(indexes);indexes[item['id']]=index
                            await emit({'tool_calls':[{'index':index,'id':item['call_id'],'type':'function','function':{'name':item['name'],'arguments':item.get('arguments','')}}]})
                            if item.get('arguments'):arguments.add(item['id'])
                        elif kind=='response.function_call_arguments.delta':
                            item_id=event['item_id'];arguments.add(item_id)
                            await emit({'tool_calls':[{'index':indexes[item_id],'function':{'arguments':event.get('delta','')}}]})
                        elif kind=='response.function_call_arguments.done' and event['item_id'] not in arguments:
                            await emit({'tool_calls':[{'index':indexes[event['item_id']],'function':{'arguments':event.get('arguments','{}')}}]})
                        elif kind in {'response.completed','response.incomplete'}:
                            final=event.get('response') or {};self.remember(target,final)
                            usage=self.usage(final);tokens=usage['completion_tokens']
                            await emit({},'tool_calls' if indexes else 'length' if kind=='response.incomplete' else 'stop')
                            await emit({},usage=usage);terminal=True;break
                        elif kind in {'response.failed','error'}:
                            await response.write(('data: '+json.dumps({'error':{'message':'Платный API прервал ответ. Автоматического повтора нет.','type':'upstream_error'}})+'\n\n').encode());terminal=True;break
                    if not terminal:
                        await response.write(b'data: {"error":{"message":"Paid API stream ended before completion","type":"incomplete_stream"}}\n\n')
                    await response.write(b'data: [DONE]\n\n');await response.write_eof();return response
        except (ClientError,asyncio.TimeoutError,ConnectionError):
            if response is not None:return response
            return web.json_response({'error':{'message':'Связь с платным API прервалась. Исход запроса неизвестен; проверьте кабинет перед повтором.','type':'outcome_unknown'}},status=400)
        except (ValueError,KeyError,TypeError):
            if response is not None:return response
            return web.json_response({'error':{'message':'Не удалось прочитать ответ платного API. Проверьте кабинет перед повтором.','type':'invalid_upstream_response'}},status=400)
        finally:
            elapsed=max(.001,time.monotonic()-started)
            self.owner.calls[target['id']]={'output_tokens':tokens,'seconds':round(elapsed,2),'time':time.time(),
                'tokens_per_second':round(tokens/max(.001,time.monotonic()-(first or started)),1) if tokens else None,
                **({'last_error':failure} if failure else {})}
