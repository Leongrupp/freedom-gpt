"""Agent positioning shared by bilingual landing pages and the practical guide."""
import html

COPY={'ru': {'title': 'Ваш ИИ-агент.<br>На вашем ПК.',
        'sub': 'Модели. Инструменты. Результат.',
        'intro': 'Freedom GPT — агент для ваших задач: код, файлы, сайты и творчество. Выбирайте совместимые '
                 'локальные модели или API, ставьте цель и следите за результатом. Русский, English и 中文.',
        'heading': 'Поручите результат.<br>Работайте с агентом.',
        'lead': 'От задачи до файлов проекта: агент использует модель для рассуждений, инструменты для '
                'действий и память для продолжения работы.',
        'preview': 'Новый релиз · 1.6.0',
        'status': 'Три языка, локальные GGUF и API, выбор моделей в одном чате. Турбо, контекст, работа с '
                  'телефона и продолжение после ошибок — в одной версии.',
        'cards': [('01',
                   'Код и проекты',
                   'Создавайте сайты и приложения: агент читает и изменяет файлы, работает в терминале и '
                   'запускает доступные проверки.'),
                  ('02',
                   'Цели и очередь',
                   'Поставьте цель с критериями готовности. Добавляйте задания в очередь и передавайте '
                   'срочную поправку текущей работе.'),
                  ('03',
                   'Ветки и память',
                   'Создайте ветку прямо у ответа. В ней сохраняются переписка и файлы, а очередь начинается '
                   'пустой. Заметки проекта остаются на диске.'),
                  ('04',
                   'Браузер рядом с чатом',
                   'Просмотр открывается во время работы агента со страницей. Видны действия и результат; '
                   'обычные браузеры также доступны через установленные инструменты.'),
                  ('05',
                   'Несколько моделей в одном чате',
                   'Выбирайте модели вручную или назначьте автоматический подбор для разных этапов: '
                   'сценарий, изображения, видео и код.'),
                  ('06',
                   'Модели под ваш ПК',
                   'Проверка CPU, RAM, GPU и свободного места помогает выбрать подходящую модель. Загрузки '
                   'возобновляются и проверяются по SHA256.'),
                  ('07',
                   'Изображения и видео',
                   'Результаты открываются в чате с превью. Локальная генерация требует отдельных моделей; '
                   'облачное видео поддерживает fal.ai.'),
                  ('08',
                   'Турбо с измерением',
                   'Режим сравнивает настройки на этом компьютере и сохраняет профиль ускорения, если он '
                   'помогает. Переключение ждёт освобождения модели.'),
                  ('09',
                   'Контекст и обдумывание',
                   'Выбирайте доступное окно контекста и поддерживаемую глубину обдумывания. Большое окно '
                   'требует больше памяти и может работать медленнее.'),
                  ('10',
                   'Продолжение после ошибок',
                   'При полном доступе агент получает до трёх автоматических продолжений со сменой подхода. '
                   'Повтор без исправлений блокируется; кнопка «Стоп» действует.'),
                  ('11',
                   'Пульт на телефоне',
                   'Включите доступ в настройках и подключите телефон через QR-код. Чаты, файлы и задания '
                   'доступны в браузере, пока компьютер работает.'),
                  ('12',
                   'Награды и уровни',
                   'Достижения, счётчики работ, опыт и игровые баллы Freedom. Это локальные награды, а не '
                   'выпущенная криптовалюта.')],
        'workflow': ['Выберите совместимую модель',
                     'Укажите проект и цель',
                     'Следите за действиями и результатом'],
        'detail': 'Как работает ИИ-агент →',
        'limits': 'Возможности зависят от модели, памяти ПК, установленных программ и выданных разрешений. '
                  'Blender и специализированные утилиты устанавливаются отдельно. Для анализа скриншотов '
                  'нужна визуальная модель. Память не безгранична; сложные результаты требуют проверки.',
        'free': 'Локальные модели работают без оплаты за токены. Сетевые функции требуют интернета; внешние '
                'API имеют собственные лимиты и тарифы.'},
 'en': {'title': 'Your AI agent.<br>On your computer.',
        'sub': 'Models. Tools. Results.',
        'intro': 'Freedom GPT is an agent for coding, files, websites and creative work. Choose compatible '
                 'local or API models, define a goal and follow the results. Русский, English and 中文.',
        'heading': 'Describe the outcome.<br>Work with an agent.',
        'lead': 'From a task to project files: the model reasons, tools perform actions and project memory '
                'helps the agent pick up work again.',
        'preview': 'New release · 1.6.0',
        'status': 'Three languages, local GGUF and API models in one chat. Turbo, context controls, a phone '
                  'companion and tool-loop recovery in one release.',
        'cards': [('01',
                   'Code and projects',
                   'Build websites and applications: the agent reads and edits files, uses the terminal and '
                   'runs available checks.'),
                  ('02',
                   'Goals and task queue',
                   'Define an outcome and acceptance criteria. Queue follow-up tasks and steer the current '
                   'task with an urgent correction.'),
                  ('03',
                   'Branches and memory',
                   'Branch directly from a reply. Keep its conversation and files with a fresh empty queue. '
                   'Project notes stay on disk.'),
                  ('04',
                   'Browser beside the chat',
                   'The preview opens while the agent works with a page. Review its actions and results; '
                   'installed tools can also use ordinary browsers.'),
                  ('05',
                   'Multiple models in one chat',
                   'Choose models yourself or allow automatic selection for different stages: scripts, '
                   'images, video and code.'),
                  ('06',
                   'Models for your hardware',
                   'CPU, RAM, GPU and disk checks help select a model. Interrupted downloads resume and '
                   'SHA256 hashes verify the files.'),
                  ('07',
                   'Images and video',
                   'View generated media previews in chat. Local generation needs separate models; cloud '
                   'video supports fal.ai.'),
                  ('08',
                   'Measured Turbo mode',
                   'Compare engine settings on this computer and save an acceleration profile when it helps. '
                   'Switching waits for an idle model.'),
                  ('09',
                   'Context and reasoning',
                   'Select an available context window and supported reasoning depth. Larger contexts need '
                   'more memory and may be slower.'),
                  ('10',
                   'Recovery after tool loops',
                   'Full access permits up to three automatic continuations with instructions to change '
                   'strategy. Unchanged repetitions are blocked; Stop remains effective.'),
                  ('11',
                   'Phone companion',
                   'Enable access in Settings and pair a phone with a QR code. Use chats, files and tasks in '
                   'the browser while your computer stays on.'),
                  ('12',
                   'Achievements and levels',
                   'Earn achievements, activity counts, XP and Freedom game points. These are local rewards, '
                   'not an issued cryptocurrency.')],
        'workflow': ['Choose a compatible model',
                     'Select a project and a goal',
                     'Review actions and the result'],
        'detail': 'How the AI agent works →',
        'limits': 'Capabilities depend on the model, PC memory, installed software and granted permissions. '
                  'Blender and specialist utilities are separate installations. Screenshot analysis needs a '
                  'vision model. Memory is finite and complex results need verification.',
        'free': 'Local models have no per-token charge from Freedom GPT. Online features require internet; '
                'external APIs have their own limits and pricing.'}}

def configure(text,copies):
 for lang,d in COPY.items():
  text[lang].update(title=d['title'],titleSub=d['sub'],intro=d['intro'],heroSmall='Модели · Инструменты · Память' if lang=='ru' else 'Models · Tools · Memory',workspaceText=d['lead'])
  copies[lang]['faq']=[(q,a) for q,a in copies[lang]['faq'] if q not in ('Как приходят обновления?','How do updates arrive?')]
  copies[lang]['faq'].append(('Как обновляется новая версия агента?' if lang=='ru' else 'How does the new agent version update?', 'Проверка и загрузка начинаются только по кнопке «Проверить обновления». Подписанная установка ждёт завершения задач и сохраняет пользовательские данные.' if lang=='ru' else 'Checking and downloading start only when you click Check for updates. Signed installation waits for idle tasks and preserves user data.'))

def section(lang):
 d=COPY[lang];e=html.escape
 cards=''.join(f'<article><span class="agent-index">{n}</span><h3>{e(title)}</h3><p>{e(body)}</p></article>' for n,title,body in d['cards'])
 flow=''.join(f'<li><span>0{i+1}</span>{e(label)}</li>' for i,label in enumerate(d['workflow']))
 guide=('/en' if lang=='en' else '')+'/guides/ai-agent/'
 return f'''<section class="section wrap agent-section" id="features"><div class="section-heading"><div><div class="eyebrow">FREEDOM GPT / AI AGENT</div><h2>{d['heading']}</h2></div><p>{e(d['lead'])}</p></div><div class="agent-preview-note"><span>{e(d['preview'])}</span><p>{e(d['status'])}</p></div><div class="agent-capabilities">{cards}</div><ol class="agent-flow">{flow}</ol><div class="agent-fine-print"><p>{e(d['limits'])}</p><a class="text-link" href="{guide}">{e(d['detail'])}</a></div></section>'''

def gallery(lang):
 en=lang=='en';e=html.escape
 title='The real agent.<br>In your workspace.' if en else 'Настоящий агент.<br>В вашем рабочем окне.'
 lead='Actual Freedom GPT 1.5.0 on Windows 11. The agent created ExpenseLab, accepted a correction, ran six tests and completed its goal.' if en else 'Реальная Freedom GPT 1.5.0 на Windows 11. Агент создал ExpenseLab, учёл поправку, выполнил шесть тестов и завершил цель.'
 labels=[('chat','Code, chats and editable files' if en else 'Код, чаты и редактирование файлов'),('goal','Goals, acceptance criteria and history' if en else 'Цели, критерии готовности и история'),('models','Model suggestions for your hardware' if en else 'Подбор моделей под ваш компьютер')]
 figures=[]
 for kind,label in labels:
  src=f'/media/screenshots/{"overview" if kind=="chat" else kind}-{lang}.png'
  figures.append(f'<figure class="panel-shot panel-shot-{kind}"><a href="{src}" target="_blank" rel="noopener" aria-label="{e(label)} — {"open screenshot" if en else "открыть снимок"}"><img src="{src}" width="1536" height="1000" loading="lazy" decoding="async" alt="{e(label)} · Freedom GPT 1.5.0 · {"English interface" if en else "русский интерфейс"}"></a><figcaption><span>{e(label)}</span><a href="{src}" target="_blank" rel="noopener">{"Full size ↗" if en else "Открыть ↗"}</a></figcaption></figure>')
 note='Screenshots show the Windows interface, with a Russian example conversation. Mac and Linux use the same web interface; native Mac execution remains unverified. The displayed PC is an example, not a minimum requirement.' if en else 'Снимки сделаны в Windows на демонстрационном проекте, без личных чатов. На Mac и Linux используется тот же веб-интерфейс; запуск на настоящем Mac ещё не проверен. Показанное железо — пример, а не минимальное требование.'
 return f'''<section class="section wrap panel-gallery" id="workspace"><div class="section-heading"><div><div class="eyebrow">FREEDOM GPT / {"ACTUAL APP" if en else "РЕАЛЬНОЕ ПРИЛОЖЕНИЕ"}</div><h2>{title}</h2></div><p>{e(lead)}</p></div><div class="panel-gallery-grid">{''.join(figures)}</div><details class="panel-workflow"><summary>{"See the task queue and an urgent correction" if en else "Посмотреть очередь и срочную поправку во время работы"}</summary><a href="/media/screenshots/agent-working-ru.png" target="_blank" rel="noopener"><img src="/media/screenshots/agent-working-ru.png" width="1536" height="1000" loading="lazy" alt="{"Actual task queue and active-task steering, Russian interface" if en else "Настоящая очередь заданий и поправка текущей задаче"}"></a></details><p class="panel-capture-note">{e(note)}</p></section>'''


def release_panels(lang):
 en=lang=='en'
 title='New controls. Less friction.' if en else 'Новые возможности. Меньше лишнего.'
 lead='Real 1.6.0 Windows preview from an isolated installation: compact settings, notifications, achievements and phone pairing. No private chats or keys.' if en else 'Настоящая Windows-сборка 1.6.0 в отдельной установке: настройки, уведомления, достижения и подключение телефона. Без личных чатов и ключей.'
 labels=[('notifications-160','Reply notifications and separate sound control' if en else 'Уведомления об ответах и отдельный звук'),('rewards-160','Achievements and creator progression' if en else 'Достижения и развитие создателя'),('phone-160','Pair a phone when you need it' if en else 'Подключите телефон, когда нужно')]
 images=''.join('<figure class="release-panel"><a href="/media/screenshots/'+name+'.png" target="_blank" rel="noopener"><img src="/media/screenshots/'+name+'.png" alt="'+html.escape(label)+'" loading="lazy" decoding="async"></a><figcaption>'+html.escape(label)+'</figcaption></figure>' for name,label in labels)
 return '<section class="section wrap release-panels"><div class="section-heading"><div><div class="eyebrow">FREEDOM GPT / 1.6.0</div><h2>'+title+'</h2></div><p>'+lead+'</p></div><div class="release-panels-grid">'+images+'</div></section>'


def decorate(page,lang):
 start=page.index('<section class="section wrap" id="workspace">');end=page.index('</section>',start)+len('</section>')
 page=page[:start]+gallery(lang)+release_panels(lang)+page[end:]
 start=page.index('<section class="section wrap feature-section" id="features">');end=page.index('</section>',start)+len('</section>')
 page=page[:start]+section(lang)+page[end:]
 return page.replace('</head>','<link rel="stylesheet" href="/agent.css?v=20261022-showcase2"></head>')

def guide(lang):
 d=COPY[lang];e=html.escape;en=lang=='en'
 body=f'<p>{e(d["lead"])}</p><p><strong>{e(d["preview"])}</strong></p><p>{e(d["status"])}</p>'
 for _,title,text in d['cards']:body+=f'<section><h2>{e(title)}</h2><p>{e(text)}</p></section>'
 title='A practical first task' if en else 'Первое практическое задание'
 prompt='Create a small local website in this project folder. Start with a plan, implement it, run available tests and show the page in preview. Stop before external publication.' if en else 'Создай небольшой локальный сайт в этой папке проекта. Сначала составь план, реализуй его, выполни доступные тесты и покажи страницу в просмотре. Остановись перед публикацией в интернете.'
 body+=f'<section><h2>{title}</h2><p>{e(prompt)}</p></section>'
 body+=f'<section><h2>{"Control and limits" if en else "Контроль и ограничения"}</h2><p>{e(d["limits"])}</p><p>{e(d["free"])}</p><p>{"Use narrow permissions, project backups and your own acceptance checks. A completed goal is a model verdict, not a guarantee of correctness." if en else "Используйте подходящий режим доступа, резервные копии и свою проверку результата. Завершение цели — оценка агента, а не гарантия правильности."}</p></section>'
 body+=f'<section><h2>{"The real interface" if en else "Настоящий интерфейс"}</h2><a href="/media/screenshots/chat-{lang}.png"><img class="panel-guide-image" src="/media/screenshots/chat-{lang}.png" width="1536" height="1000" loading="lazy" alt="Freedom GPT 1.5.0 — {"code and file editing on Windows" if en else "код и редактор файлов в Windows"}"></a><p>{"Actual Windows capture. A neutral demo project, with the Russian conversation preserved." if en else "Снимок работающей Windows-версии на демонстрационном проекте ExpenseLab."}</p></section>'
 return body
