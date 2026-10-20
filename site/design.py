"""Freedom GPT graphite and silver presentation, shared by both languages."""
import html,json,pathlib
from download_ui import brand,quick_downloads,platform_cards
from install_guide import guides

VERSION = 'install-guide-1.4.2-r3'
PROJECT=json.loads((pathlib.Path(__file__).parent/'project.json').read_text(encoding='utf-8'))
SITE=PROJECT['support']['website']
TELEGRAM=PROJECT['support']['telegram']
REPO = 'https://github.com/Leongrupp/freedom-gpt'
BTC = 'bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6'
TEXT = {
 'ru': {
  'nav': ['Пространство', 'Возможности', 'Модели', 'Установка'], 'menu': 'Открыть меню', 'skip': 'К содержимому',
  'eyebrow': 'БЕСПЛАТНЫЙ ЛОКАЛЬНЫЙ ИИ', 'title': 'Свобода<br>создавать.', 'titleSub': 'На вашем компьютере.',
  'intro': 'От первой идеи до работающего кода. Чаты, файлы и генерация изображений — в одном локальном пространстве.',
  'explore': 'Познакомиться ближе', 'heroAlt': 'Скульптурное ядро из тёмного титана и светящегося стекла',
  'heroNote': 'ВАШ КОМПЬЮТЕР. ВАШ ИНТЕЛЛЕКТ.', 'heroSmall': 'Локальные модели · Полный контроль',
  'principles': [('Всё начинается с вашего ПК', 'Модели работают на вашем CPU и GPU.'), ('Данные остаются у вас', 'Локальные чаты, файлы и история проектов.'), ('Свобода выбора', 'Бесплатное приложение. Открытый код.')],
  'workspace': 'РАБОЧЕЕ ПРОСТРАНСТВО', 'workspaceTitle': 'Большие идеи.<br>Собранные в одном окне.',
  'workspaceText': 'Сосредоточьтесь на задаче. Важное о проекте, файлы и диалог с моделью всегда рядом.',
  'previewLabel': 'Иллюстрация интерфейса', 'codeTab': 'Код и проекты', 'artTab': 'Творческая студия', 'newChat': 'Новый чат',
  'projects': 'ПРОЕКТЫ', 'chats': 'НЕДАВНИЕ', 'project': 'Мой следующий проект', 'chatOne': 'Новая идея', 'chatTwo': 'Работа с файлами',
  'request': 'Создай лаконичную стартовую страницу моего проекта.',
  'response': 'Начнём с чистой структуры. Вот компонент первого экрана:',
  'codeCopy': 'Копировать', 'codeCopied': 'Скопировано', 'prompt': 'Что будем создавать дальше?', 'local': 'На этом компьютере', 'context': 'Контекст до 65К',
  'artCaption': 'Визуальная концепция Freedom GPT', 'artSample': 'Концепт для сайта. Не результат теста локальной модели.',
  'featureTitle': 'Больше возможностей.<br>Меньше лишнего.',
  'features': [('code', 'Код с продолжением', 'Пишите программы, сохраняйте диалоги и возвращайтесь к своим проектам. Скопировать фрагмент кода — одно нажатие.'), ('image', 'Своя студия изображений', 'Подключите комплект Qwen Image и создавайте иллюстрации на своём компьютере. Вычисления остаются локальными.'), ('folder', 'Файлы в контексте', 'Прикрепляйте документы и изображения к диалогу. Возможности анализа зависят от выбранной модели.')],
  'creative': 'ТВОРЧЕСКАЯ СТУДИЯ', 'creativeTitle': 'Придайте форму<br>своему воображению.',
  'creativeText': 'От обложки проекта до новой визуальной идеи. Опишите замысел — отдельная модель изображений возьмёт на себя расчёты.',
  'creativeTags': ['Текст → изображение', 'Локальная генерация', 'История работ'], 'creativeLink': 'Как подключить модели',
  'creativeAlt': 'Серебряное кольцо над тёмным морем в футуристичном пейзаже',
  'models': 'МОДЕЛИ И ВОЗМОЖНОСТИ', 'modelsTitle': 'Ваше железо.<br>Ваш масштаб.',
  'hardwareLabel': 'ПРОВЕРКА ПРИ ПЕРВОМ ЗАПУСКЕ', 'hardwareTitle': 'Сначала знакомимся с ПК.',
  'hardwareText': 'Приложение проверяет процессор, оперативную и видеопамять, а также свободное место. Вы выбираете подходящую модель и скачиваете её из каталога.',
  'hardwareNote': 'Проверка выполняется в установленном приложении. Сайт не сканирует компьютер.',
  'hardwareNames': ['Процессор', 'Оперативная память', 'Видеопамять', 'Место на SSD'],
  'modelTags': ['Код · стандартный набор', 'Изображения · отдельный комплект', 'Чат · меньше памяти'],
  'how': 'ПРОСТО НАЧАТЬ', 'howTitle': 'Три шага.<br>И вы на своей территории.',
  'portableEyebrow': 'МЕСТО ДЛЯ ВАШЕЙ РАБОТЫ', 'portableTitle': 'Свобода —<br>это когда всё ваше.',
  'portableText': 'Приложение, модели и история могут жить в одной папке на SSD. После загрузки моделей локальная работа доступна без интернета.',
  'portableNote': 'Скорость зависит от компьютера. Перед отключением внешнего SSD остановите приложение; перенос на другой физический ПК пока не проверен.',
  'downloadTitle': 'Ваша система.<br>Ваш Freedom GPT.', 'downloadText': 'Установите Freedom GPT. Выберите модель. Создавайте своё.',
  'downloadStamp': 'БЕСПЛАТНО · WINDOWS · UBUNTU · MAC', 'supportLabel': 'НЕЗАВИСИМЫЙ ПРОЕКТ', 'faq': 'Есть вопросы?',
  'footer': 'Интеллект под вашим контролем.', 'codeLink': 'Открытый код', 'licenses': 'Лицензии', 'roadmap': 'Развиваю агента Freedom GPT, новые модели и генерацию видео. Видеостудия пока экспериментальная; продолжаю её проверку и улучшение.',
 },
 'en': {
  'nav': ['Workspace', 'Features', 'Models', 'Get started'], 'menu': 'Open navigation', 'skip': 'Skip to content',
  'eyebrow': 'FREE LOCAL AI · OPEN SOURCE', 'title': 'Freedom<br>to create.', 'titleSub': 'On your computer.',
  'intro': 'From a first idea to working code. Chats, files and image generation, together in one local workspace.',
  'explore': 'Explore the workspace', 'heroAlt': 'A sculptural core of dark titanium and luminous glass',
  'heroNote': 'YOUR COMPUTER. YOUR INTELLIGENCE.', 'heroSmall': 'Local models · Your control',
  'principles': [('Built around your PC', 'Models run on your own CPU and GPU.'), ('Your data stays with you', 'Local chats, files and project history.'), ('The freedom to choose', 'A free application. Open source code.')],
  'workspace': 'YOUR WORKSPACE', 'workspaceTitle': 'Big ideas.<br>One focused space.',
  'workspaceText': 'Stay with the task. Project context, files and your conversation with the model are always within reach.',
  'previewLabel': 'Interface illustration', 'codeTab': 'Code and projects', 'artTab': 'Creative studio', 'newChat': 'New chat',
  'projects': 'PROJECTS', 'chats': 'RECENT', 'project': 'My next project', 'chatOne': 'A new idea', 'chatTwo': 'Working with files',
  'request': 'Build a clean landing page for my project.', 'response': 'Let’s start with a clear structure. Here is the hero component:',
  'codeCopy': 'Copy code', 'codeCopied': 'Copied', 'prompt': 'What shall we create next?', 'local': 'On this computer', 'context': 'Up to 65K context',
  'artCaption': 'Freedom GPT visual concept', 'artSample': 'Website concept art. Not a local model benchmark output.',
  'featureTitle': 'More possibilities.<br>Less in the way.',
  'features': [('code', 'Code you can return to', 'Build software, save conversations and pick up your projects again. Copy a code block with a single click.'), ('image', 'Your own image studio', 'Connect the Qwen Image model pack and create artwork on your own computer. Inference stays local.'), ('folder', 'Files in context', 'Attach documents and images to your conversation. Analysis capabilities depend on the model you choose.')],
  'creative': 'CREATIVE STUDIO', 'creativeTitle': 'Give your<br>imagination form.',
  'creativeText': 'From a project cover to a new visual direction. Describe the idea and let a dedicated image model do the computation.',
  'creativeTags': ['Text → image', 'Local generation', 'Saved artwork'], 'creativeLink': 'Explore the model setup',
  'creativeAlt': 'A silver ring above an obsidian sea in a cinematic future landscape',
  'models': 'MODELS AND POSSIBILITIES', 'modelsTitle': 'Your hardware.<br>Your scale.',
  'hardwareLabel': 'FIRST-RUN HARDWARE CHECK', 'hardwareTitle': 'First, meet your computer.',
  'hardwareText': 'The app checks your processor, RAM, GPU memory and free storage. You choose a suitable model and download it from the library.',
  'hardwareNote': 'The check runs in the installed app. This website does not scan your computer.',
  'hardwareNames': ['Processor', 'System memory', 'GPU memory', 'SSD storage'],
  'modelTags': ['Code · standard pack', 'Images · separate pack', 'Chat · lighter footprint'],
  'how': 'GETTING STARTED', 'howTitle': 'Three steps.<br>Make it your own.',
  'portableEyebrow': 'ROOM FOR YOUR WORK', 'portableTitle': 'Freedom means<br>it belongs to you.',
  'portableText': 'Keep your app, models and history in one SSD folder. After downloading the models, local work is available offline.',
  'portableNote': 'Performance depends on the computer. Stop the app before disconnecting an external SSD. Moving to a different physical PC has not yet been tested.',
  'downloadTitle': 'Your system.<br>Your Freedom GPT.', 'downloadText': 'Install Freedom GPT. Choose a model. Make something yours.',
  'downloadStamp': 'FREE · WINDOWS · UBUNTU · MAC', 'supportLabel': 'AN INDEPENDENT PROJECT', 'faq': 'A few good questions.',
  'footer': 'Intelligence under your control.', 'codeLink': 'Open source', 'licenses': 'Licenses', 'roadmap': 'I am developing the Freedom GPT agent, new model options and video generation. Video Studio is experimental; testing and improvements continue.',
 }
}

def icon(name, cls=''):
 paths = {
  'arrow': '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  'download': '<path d="M12 3v12m-5-5 5 5 5-5M5 16v5h14v-5"/>',
  'code': '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-14-2 18"/>',
  'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m21 15-5-5-10 11"/>',
  'folder': '<path d="M3 7V5h6l2 3h10v12H3Z"/>',
  'plus': '<path d="M12 5v14M5 12h14"/>',
  'check': '<path d="m5 12 4 4L19 6"/>',
  'windows': '<path d="m3 5 8-1v7H3Zm10-1 8-1v8h-8ZM3 13h8v7l-8-1Zm10 0h8v8l-8-1Z"/>',
  'copy': '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
  'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
 }
 return f'<svg class="icon {cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'

def build(lang, c):
 d=TEXT[lang]
 nav=''.join(f'<a href="{href}">{label}</a>' for href,label in zip(['#workspace','#features','#models','#how'],d['nav']))
 principles=''.join(f'<div><span class="index">0{i+1} /</span><div><h3>{name}</h3><p>{body}</p></div></div>' for i,(name,body) in enumerate(d['principles']))
 features=''.join(f'<article class="feature" data-reveal><div class="feature-icon">{icon(symbol)}</div><h3>{name}</h3><p>{body}</p></article>' for symbol,name,body in d['features'])
 model_titles=['Huihui Qwen3.8 Coder','Qwen Image 2.1 Turbo','Qwen3.5 · 4B / 0.8B']
 models=''.join(f'<article class="model-row"><span class="index">0{i+1}</span><div><span class="model-tag">{d["modelTags"][i]}</span><h3>{name}</h3><p>{body}</p></div><span class="model-arrow" aria-hidden="true">↗</span></article>' for i,(name,body) in enumerate(zip(model_titles,c['modelInfo'])))
 steps=''.join(f'<article class="step" data-reveal><span class="step-number">0{i+1}</span><h3>{name}</h3><p>{body}</p></article>' for i,(name,body) in enumerate(c['steps']))
 faq=''.join(f'<details><summary>{q}<span aria-hidden="true">+</span></summary><p>{a}</p></details>' for q,a in c['faq'])
 tags=''.join(f'<span>{icon("check")}{tag}</span>' for tag in d['creativeTags'])
 hardware=''.join(f'<div><span class="hardware-led"></span><span>{name}</span><b>{["CPU", "RAM", "VRAM", "SSD"][i]}</b></div>' for i,name in enumerate(d['hardwareNames']))
 language='Русский' if lang=='ru' else 'English'
 version=PROJECT['version']
 contact='Вопросы? Напишите автору в Telegram' if lang=='ru' else 'Questions? Message the author on Telegram'
 star='Оценить проект на GitHub' if lang=='ru' else 'Star the project on GitHub'
 thanks='Спасибо каждому за отзывы, идеи и поддержку 💛' if lang=='ru' else 'Thank you for every idea, bug report and contribution 💛'
 return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark">
<title>Freedom GPT — {c['title']}</title><meta name="description" content="{html.escape(d['intro'])}"><meta property="og:title" content="Freedom GPT — {c['title']}"><meta property="og:description" content="{html.escape(d['intro'])}"><meta property="og:image" content="{SITE}/media/site/project-cover.png"><meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{SITE}{"/" if lang=="ru" else "/en/"}"><link rel="alternate" hreflang="ru" href="{SITE}/"><link rel="alternate" hreflang="en" href="{SITE}/en/"><link rel="icon" href="/freedom.svg?v={VERSION}"><link rel="preload" as="image" href="/media/site/core-hero.webp"><link rel="stylesheet" href="/premium.css?v={VERSION}"><script type="module" src="/app.js?v={VERSION}"></script></head>
<body><a class="skip-link" href="#main">{d['skip']}</a>
<header class="header" id="top"><div class="header-inner"><a class="brand" href="{'/' if lang=='ru' else '/en/'}" aria-label="Freedom GPT"><img src="/freedom.svg?v={VERSION}" width="32" height="32" alt=""><span>Freedom <b>GPT</b></span></a><nav class="desktop-nav" aria-label="{'Навигация' if lang=='ru' else 'Navigation'}">{nav}</nav><div class="header-actions"><a class="header-repository" href="{REPO}" target="_blank" rel="noopener noreferrer" aria-label="GitHub · Freedom GPT">{brand("github")}<span>GitHub</span></a><div class="site-languages" aria-label="Language"><a href="/" {'aria-current="page"' if lang=='ru' else ''}>RU</a><a href="/en/" {'aria-current="page"' if lang=='en' else ''}>EN</a></div><a class="header-download" href="#download">{icon('download')}<span>{'Скачать' if lang=='ru' else 'Download'}</span></a><button class="menu-toggle" aria-label="{d['menu']}" aria-expanded="false" aria-controls="mobile-nav">{icon('menu')}</button></div></div><nav id="mobile-nav" class="mobile-nav" aria-label="{'Мобильная навигация' if lang=='ru' else 'Mobile navigation'}" hidden>{nav}</nav></header>
<main id="main">
<section class="hero wrap" aria-labelledby="hero-title"><div class="hero-art" aria-hidden="true"><img src="/media/site/core-hero.webp" alt="" width="1536" height="1024" fetchpriority="high"></div><div class="hero-copy"><div class="eyebrow"><i class="status-dot"></i>{d['eyebrow']}</div><h1 id="hero-title">{d['title']}</h1><div class="hero-subtitle">{d['titleSub']}</div><p class="hero-description">{d['intro']}</p>{quick_downloads(lang,version,REPO)}<span class="hero-release" id="hero-release">v{version} · Windows / macOS / Ubuntu · RU / EN</span><div class="hero-community"><a href="{REPO}" target="_blank" rel="noopener noreferrer">{brand('github')}{'Open source on GitHub' if lang=='en' else 'Открытый проект на GitHub'}{icon('arrow')}</a><a href="{TELEGRAM}" target="_blank" rel="noopener noreferrer">{brand('telegram')}{'Telegram support' if lang=='en' else 'Поддержка в Telegram'}</a></div></div><div class="hero-art-label"><span class="crosshair">+</span><div>{d['heroNote']}<small>{d['heroSmall']}</small></div><span class="hero-art-no">F / 01</span></div></section>
<section class="principles wrap" aria-label="Freedom GPT">{principles}</section>
<section class="project-strip wrap" aria-label="{'Open source community' if lang=='en' else 'Открытый проект и поддержка'}"><div class="project-strip-copy">{brand('github')}<div><strong>{'Free to use. Open to your ideas.' if lang=='en' else 'Бесплатно. Открыто. Для ваших идей.'}</strong><p>{'Explore the source, follow releases and help shape what comes next.' if lang=='en' else 'Исходники, релизы и развитие проекта — в открытом доступе.'}</p></div></div><div class="project-strip-actions"><a class="button secondary" href="{REPO}" target="_blank" rel="noopener noreferrer">{'Explore GitHub' if lang=='en' else 'Проект на GitHub'}{icon('arrow')}</a><a class="text-link" href="{TELEGRAM}" target="_blank" rel="noopener noreferrer">{'Need help? @AI1rus' if lang=='en' else 'Нужна помощь? @AI1rus'}</a></div></section>

<section class="section wrap" id="workspace"><div class="section-heading" data-reveal><div><div class="eyebrow"><span>01 /</span>{d['workspace']}</div><h2>{d['workspaceTitle']}</h2></div><p>{d['workspaceText']}</p></div>
<div class="workspace-showcase" data-reveal><div class="preview-controls"><div class="preview-tabs" role="tablist" aria-label="{d['previewLabel']}"><button id="tab-code" role="tab" aria-selected="true" aria-controls="preview-code" data-preview-tab="code">{icon('code')}{d['codeTab']}</button><button id="tab-art" role="tab" aria-selected="false" aria-controls="preview-art" tabindex="-1" data-preview-tab="art">{icon('image')}{d['artTab']}</button></div><span class="preview-illustration">{d['previewLabel']}</span></div>
<div class="app-window"><aside class="app-sidebar"><div class="mini-brand"><img src="/freedom.svg?v={VERSION}" width="21" height="21" alt="">Freedom GPT</div><div class="mini-new">{icon('plus')}{d['newChat']}</div><span class="mini-section">{d['projects']}</span><div class="mini-project">{icon('folder')}{d['project']}</div><span class="mini-section">{d['chats']}</span><div class="mini-chat selected">{d['chatOne']}</div><div class="mini-chat">{d['chatTwo']}</div><div class="mini-offline"><i class="status-dot"></i>LOCAL WORKSPACE</div></aside><div class="app-main"><div class="app-top"><span>{d['project']}</span><span><i class="status-dot"></i>Huihui Coder</span></div>
<div class="preview-panel" id="preview-code" role="tabpanel" aria-labelledby="tab-code"><div class="sample-request">{d['request']}</div><div class="sample-response"><img src="/freedom.svg?v={VERSION}" width="26" height="26" alt=""><div><strong>Freedom GPT</strong><p>{d['response']}</p><div class="code-block"><div class="code-bar"><span>Hero.tsx</span><button id="copy-code" data-copied="{d['codeCopied']}" aria-label="{d['codeCopy']}">{icon('copy')}<span>{d['codeCopy']}</span></button></div><pre><code id="sample-code"><span class="syntax-purple">export default function</span> <span class="syntax-blue">Hero</span>() {{
  <span class="syntax-purple">return</span> (
    &lt;<span class="syntax-blue">main</span> className=<span class="syntax-green">"your-next-idea"</span>&gt;
      &lt;<span class="syntax-blue">h1</span>&gt;Create something yours.&lt;/<span class="syntax-blue">h1</span>&gt;
      &lt;<span class="syntax-blue">p</span>&gt;Built with freedom.&lt;/<span class="syntax-blue">p</span>&gt;
    &lt;/<span class="syntax-blue">main</span>&gt;
  );
}}</code></pre></div></div></div></div>
<div class="preview-panel art-panel" id="preview-art" role="tabpanel" aria-labelledby="tab-art" hidden><img src="/media/site/creative-world.webp" width="1536" height="1024" alt="{d['creativeAlt']}" loading="lazy"><div><strong>{d['artCaption']}</strong><span>{d['artSample']}</span></div></div>
<div class="mini-composer"><span>{d['prompt']}</span><div><span>{icon('plus')}<small>{d['local']}</small></span><span class="mini-send">↑</span></div></div><div class="mini-footer"><span>{d['context']}</span><span>CPU + GPU · LOCAL</span></div></div></div></div></section>

<section class="section wrap feature-section" id="features"><div class="section-heading" data-reveal><div><div class="eyebrow"><span>02 /</span>FREEDOM TO BUILD</div><h2>{d['featureTitle']}</h2></div></div><div class="feature-grid">{features}</div></section>

<section class="creative-section wrap"><figure class="creative-visual" data-reveal><img src="/media/site/creative-world.webp" alt="{d['creativeAlt']}" width="1536" height="1024" loading="lazy"><figcaption><span>FREEDOM / IMAGINATION</span><span>{d['artCaption']}</span></figcaption></figure><div class="creative-copy" data-reveal><div class="eyebrow">{d['creative']}</div><h2>{d['creativeTitle']}</h2><p>{d['creativeText']}</p><div class="creative-tags">{tags}</div><a class="text-link" href="#models">{d['creativeLink']}{icon('arrow')}</a></div></section>

<section class="section wrap" id="models"><div class="section-heading" data-reveal><div><div class="eyebrow"><span>03 /</span>{d['models']}</div><h2>{d['modelsTitle']}</h2></div><p>{c['modelsNote']}</p></div><div class="hardware-panel" data-reveal><div class="hardware-copy"><span class="micro-label">{d['hardwareLabel']}</span><h3>{d['hardwareTitle']}</h3><p>{d['hardwareText']}</p><small>{d['hardwareNote']}</small></div><div class="hardware-diagram"><div class="chip-illustration" aria-hidden="true"><span>F<span class="chip-dot">.</span></span><i></i></div><div class="hardware-list">{hardware}</div></div></div><div class="models-list">{models}</div><div class="model-mirrors" id="model-mirrors" hidden></div></section>

<section class="section wrap how-section" id="how"><div class="section-heading" data-reveal><div><div class="eyebrow"><span>04 /</span>{d['how']}</div><h2>{d['howTitle']}</h2></div></div><div class="steps-grid">{steps}</div></section>

<section class="portable-section wrap" data-reveal><div class="portable-glyph" aria-hidden="true"><span>FREEDOM GPT</span><div class="drive-lines"></div><b>YOUR WORKSPACE<br>GOES WITH YOU.</b><div><i class="status-dot"></i>LOCAL / SSD</div></div><div class="portable-copy"><div class="eyebrow">{d['portableEyebrow']}</div><h2>{d['portableTitle']}</h2><p>{d['portableText']}</p><small>{d['portableNote']}</small></div></section>

<section class="download-section" id="download"><div class="download-inner wrap"><div class="download-orbit" aria-hidden="true"></div><div class="eyebrow">{d['downloadStamp']}</div><h2>{d['downloadTitle']}</h2><p>{'Choose your OS and download the app. Python and engines are included; models download separately.' if lang=='en' else 'Выберите систему и скачайте приложение. Python и движки уже внутри; модели скачиваются отдельно.'}</p><div class="download-free"><span class="status-dot"></span>{'Free to download and use · English / Русский' if lang=='en' else 'Бесплатно скачивать и пользоваться · Русский / English'}</div><div class="download-details" id="download-details" aria-live="polite">v{version} · Windows / macOS / Ubuntu</div><section class="platform-downloads" id="platform-downloads" aria-label="Operating systems">{platform_cards(lang,version,REPO)}</section>{guides(lang,version,REPO)}<div class="download-footer-links"><a href="{REPO}/releases">{brand('github')}{'All releases on GitHub' if lang=='en' else 'Все релизы на GitHub'}{icon('arrow')}</a><a id="checksum-download" href="{REPO}/releases/latest/download/SHA256SUMS.txt">{c['hashes']}{icon('arrow')}</a><a href="{TELEGRAM}" target="_blank" rel="noopener noreferrer">{brand('telegram')}{'Installation help' if lang=='en' else 'Помощь с установкой'}{icon('arrow')}</a></div><p class="requirements">{'Check each build’s requirements above. Model weights download separately. For the standard coder, plan around 32 GB RAM, 16 GB VRAM and 35 GB+ SSD space. GPU drivers are installed separately.' if lang=='en' else 'Требования и ограничения каждой сборки указаны выше. Веса моделей скачиваются отдельно. Ориентир для стандартной модели кода: 32 ГБ RAM, 16 ГБ VRAM и от 35 ГБ на SSD. Видеодрайвер устанавливается отдельно.'}</p></div></section>

<section class="section wrap support-section" id="support"><div><div class="eyebrow">{d['supportLabel']}</div><h2>{c['support']}</h2><p>{c['supportText']}</p><div class="community-links"><a href="{TELEGRAM}" target="_blank" rel="noopener noreferrer">{contact} ↗</a><a href="{REPO}" target="_blank" rel="noopener noreferrer">☆ {star}</a></div><small class="community-thanks">{thanks}</small></div><div class="donation-box"><div class="donation-top"><span class="btc-mark" aria-hidden="true">₿</span><span>BITCOIN<span>BTC · ON-CHAIN</span></span></div><code>{BTC}</code><button class="button secondary" id="copy-donation" data-copied="{c['copied']}">{icon('copy')}{c['copy']}</button><span id="copy-status" role="status" aria-live="polite"></span></div></section>
<section class="section wrap faq"><div class="eyebrow">FAQ</div><h2>{d['faq']}</h2><div class="faq-list">{faq}</div><p class="roadmap">{d['roadmap']}</p></section>
</main><footer class="footer wrap"><div><a class="brand" href="#top"><img src="/freedom.svg?v={VERSION}" width="30" height="30" alt=""><span>Freedom <b>GPT</b></span></a><p>{d['footer']}</p></div><div class="footer-links"><a href="{TELEGRAM}">Telegram ↗</a><a href="{REPO}">{d['codeLink']} ↗</a><a href="{REPO}/blob/main/NOTICE">{d['licenses']} ↗</a><a href="{'/en/' if lang=='ru' else '/'}">{'English' if lang=='ru' else 'Русский'}</a><span>© 2026 Freedom GPT</span></div></footer></body></html>'''
