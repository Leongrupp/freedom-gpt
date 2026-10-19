"""Create missing project-memory files and bind one Hermes session; never overwrite originals."""
import bootstrap
import argparse,json,os,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TEMPLATES={
'REQUIREMENTS.md': '# Requirements\n\n## Original goal\nNot recorded yet. Read the user request; do not invent requirements.\n\n## Required features\n- To be established from the user request.\n\n## Constraints and acceptance criteria\n- All project artifacts stay inside Freedom GPT workspaces.\n- Do not store credentials in these documents.\n\n## Approved changes to requirements\n- None recorded.\n',
'ARCHITECTURE.md': '# Architecture\n\n## Current implementation\nNot inspected yet. Describe the existing code before proposing changes.\n\n## Modules and responsibilities\n- Pending inspection.\n\n## Interfaces, data and dependencies\n- Pending inspection.\n\n## Build and run commands\n- Record verified commands only.\n',
'.hermes/TASKS.md': '# Tasks\n\nUse stable IDs (T001, T002). States: TODO / IN_PROGRESS / BLOCKED / DONE.\nA DONE task needs changed-file paths and verification evidence.\n\n| ID | State | Task | Dependencies / evidence |\n|---|---|---|---|\n| T001 | TODO | Read the original request and inspect the project | No implementation claimed |\n',
'.hermes/STATE.md': '# Project checkpoint\n\n## Original goal and constraints\nNot recorded yet; retrieve the actual user request.\n\n## Current task\nNo coding task has been started by this initializer.\n\n## Changed files and verified results\nOnly missing project-memory templates were created. No application tests run.\n\n## Blockers and unfinished work\nInspect the source and requirements.\n\n## Next concrete step\nRead REQUIREMENTS.md and .hermes/TASKS.md, inspect source files, record the next authorized task.\n\n## Recovery\nRecord session ID, checkpoint path and relevant Git commit here.\n',
'.hermes/DECISIONS.md': '# Decision log\n\nAppend dated decisions with reasons and affected files. Preserve old entries; append corrections.\n\nNo architectural decisions recorded yet.\n'}
def initialize(project,session=None):
    project=Path(project).resolve(); allowed=(ROOT/'workspaces').resolve()
    if not project.is_relative_to(allowed) :raise ValueError('Choose a project folder inside Freedom GPT workspaces')
    if not project.is_dir():raise ValueError('Project directory must already exist')
    created=[]
    for relative,content in TEMPLATES.items():
        path=project/relative
        if not path.resolve().is_relative_to(project):raise ValueError('Refusing a memory path outside the project')
        path.parent.mkdir(parents=True,exist_ok=True)
        try:
            with path.open('x',encoding='utf-8') as f:f.write(content);f.flush();os.fsync(f.fileno())
            created.append(relative)
        except FileExistsError:pass
    if session:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',session):raise ValueError('Invalid session ID')
        directory=ROOT/'stack/hermes-runtime/continuity'/session;directory.mkdir(parents=True,exist_ok=True)
        target=directory/'project.json';temporary=directory/('project-'+str(os.getpid())+'.tmp')
        with temporary.open('w',encoding='utf-8') as f:json.dump({'project':str(project)},f);f.flush();os.fsync(f.fileno())
        os.replace(temporary,target)
    return {'project':str(project),'created':created,'session':session}
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--project',required=True);parser.add_argument('--session')
    args=parser.parse_args();print(json.dumps(initialize(args.project,args.session),ensure_ascii=False))
