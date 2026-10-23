"""Agent-side adapter for the app's optional account broker."""
import asyncio,json,pathlib,urllib.error,urllib.request

def register(ctx):
    async def handle(args,**kwargs):
        def send():
            folder=pathlib.Path(__file__).parent
            root=(folder/json.loads((folder/'runtime.json').read_text(encoding='utf-8'))['app_relative']).resolve()
            binding=json.loads((root/'data/accounts-control.json').read_text(encoding='utf-8'))
            query=urllib.request.Request(binding['url'],data=json.dumps(args).encode(),method='POST',
                headers={'Authorization':'Bearer '+binding['key'],'Content-Type':'application/json'})
            try:
                with urllib.request.urlopen(query,timeout=45) as response:return json.load(response)
            except urllib.error.HTTPError as error:
                try:return {'error':json.load(error).get('error','GitHub request failed')}
                except ValueError:return {'error':'GitHub request failed'}
            except OSError:return {'error':'Open Freedom GPT to use the optional GitHub connection.'}
        return json.dumps(await asyncio.to_thread(send),ensure_ascii=False)
    schema={'name':'github_workspace','description':'Use the GitHub account explicitly connected in Freedom GPT settings. Credentials stay inside the app. Inspect/list repos and files; create a repository (private by default), branches, commit project files, draft PRs and issues when writing is enabled by the owner. Follow the user request and normal approval policy before publishing. Never ask for or print tokens. Accounts are optional; local work remains available offline.',
        'parameters':{'type':'object','properties':{
            'action':{'type':'string','enum':['status','list_repositories','repository','list_files','read_file','create_repository','create_branch','write_file','create_pull_request','create_issue']},
            'repository':{'type':'string','description':'owner/repository'},'name':{'type':'string'},'description':{'type':'string'},'private':{'type':'boolean','default':True},
            'path':{'type':'string','description':'Relative repository file path'},'local_path':{'type':'string','description':'Existing project file in the workspace to commit'},'content':{'type':'string'},
            'branch':{'type':'string'},'base':{'type':'string'},'head':{'type':'string'},'message':{'type':'string','description':'Commit message'},'expected_sha':{'type':'string'},
            'title':{'type':'string'},'body':{'type':'string'},'draft':{'type':'boolean','default':True},'limit':{'type':'integer','minimum':1,'maximum':100}},'required':['action']}}
    ctx.register_tool(name='github_workspace',toolset='terminal',schema=schema,handler=handle,is_async=True,description='Optional GitHub repositories and commits',emoji='🐙')
