"""Shared, accessible platform download markup with a working no-JavaScript fallback."""
import html,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
BRANDS=json.loads((ROOT/'brand-icons.json').read_text(encoding='utf-8'))
SYSTEMS=[
 ('windows-x64','windows','Windows','10 / 11 · x64','FreedomGPT-Setup-{v}.exe'),
 ('macos-arm64','apple','macOS','M1+ · macOS 26.2+','FreedomGPT-{v}-macOS-AppleSilicon.zip'),
 ('ubuntu-x64','ubuntu','Ubuntu Linux','24.04 · x64','FreedomGPT-Setup-{v}-Ubuntu-x64.run'),
]
def brand(name,cls=''):
    paths=['M2 3h9v8H2zm11 0h9v8h-9zM2 13h9v8H2zm11 0h9v8h-9z'] if name=='windows' else BRANDS[name]['paths']
    return f'<svg class="icon brand-icon {html.escape(cls)}" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">'+''.join(f'<path d="{html.escape(p,quote=True)}"/>' for p in paths)+'</svg>'
def arrow():
    return '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m-5-5 5 5 5-5M5 17v4h14v-4"/></svg>'
def quick_downloads(lang,version,repo):
    links=[]
    for target,mark,title,detail,pattern in SYSTEMS:
        title='Ubuntu' if target=='ubuntu-x64' else title
        if target=='macos-arm64':detail='M1+ · Preview' if lang=='en' else 'M1+ · тестовая'
        url=repo+'/releases/download/v'+version+'/'+pattern.format(v=version)
        label=('Download for ' if lang=='en' else 'Скачать для ')+title
        links.append(f'<a class="system-download" data-platform-download="{target}" href="{url}" aria-label="{label}">{brand(mark)}<span><strong>{title}</strong><small>{detail}</small></span>{arrow()}</a>')
    return '<div class="hero-platforms" aria-label="'+('Download for your operating system' if lang=='en' else 'Скачать для своей системы')+'">'+''.join(links)+'</div>'
def file_label(name,lang,primary=False):
    if name.endswith('.exe'):return 'Download EXE' if lang=='en' else 'Скачать EXE'
    if name.endswith('.run'):return 'Download installer' if lang=='en' else 'Скачать установщик'
    if 'macOS' in name:return 'Download for Mac' if lang=='en' else 'Скачать для Mac'
    if name.endswith('.deb'):return 'DEB package' if lang=='en' else 'Пакет DEB'
    if name.endswith('.tar.gz'):return 'Portable TAR.GZ' if lang=='en' else 'Переносимый TAR.GZ'
    return 'Portable ZIP' if lang=='en' else 'Переносимый ZIP'
def file_link(file,lang,repo,version,primary=False):
    url=repo+'/releases/download/v'+version+'/'+file['name'];size=f"{file['bytes']/1024**3:.2f}"+(' GB' if lang=='en' else ' ГБ')
    cls='platform-primary' if primary else 'platform-alternative'
    return f'<a class="{cls}" href="{url}"><span>{file_label(file["name"],lang,primary)}<small>{size}</small></span>{arrow()}</a>'
def platform_cards(lang,version,repo):
    en=lang=='en'
    data=json.loads((ROOT.parent/'release/platforms'/version/'platforms.json').read_text(encoding='utf-8'))
    matrix={p['id']:p for p in data['platforms']};cards=[]
    for target,mark,title,detail,pattern in SYSTEMS:
        item=matrix[target];primary=pattern.format(v=version);files=sorted(item['files'],key=lambda f:(f['name']!=primary,f['name']))
        badge=('Preview' if en else 'Экспериментальная') if target=='macos-arm64' else ('Available' if en else 'Доступно')
        summary={
          'windows-x64':('An installer or a portable workspace. Choose a folder and make it yours.' if en else 'Установщик или переносимая версия. Выберите папку и начните свой проект.'),
          'macos-arm64':('A local workspace for Apple Silicon. Read the preview requirements before installing.' if en else 'Локальный ИИ для Apple Silicon. Перед установкой проверьте требования сборки.'),
          'ubuntu-x64':('A standalone installer, a DEB package or an archive. Choose your preferred format.' if en else 'Самостоятельный установщик, пакет DEB или архив. Выберите удобный формат.'),
        }[target]
        note=item['note_en' if en else 'note_ru']
        links=''.join(file_link(f,lang,repo,version,i==0) for i,f in enumerate(files))
        cards.append(f'<article class="platform-card" data-platform-card="{target}"><div class="platform-card-top"><span class="platform-mark">{brand(mark)}</span><span class="platform-status {"preview" if target=="macos-arm64" else ""}">{badge}</span></div><h4>{title}</h4><div class="platform-system">{detail}</div><p class="platform-summary">{summary}</p><div class="platform-files">{links}</div><p class="platform-note">{note}</p></article>')
    return '<div class="platform-section-heading"><h3>'+('Choose your operating system' if en else 'Выберите свою систему')+'</h3><span>'+('One project. Three platforms.' if en else 'Один проект. Три платформы.')+'</span></div><div class="platform-grid">'+''.join(cards)+'</div>'
