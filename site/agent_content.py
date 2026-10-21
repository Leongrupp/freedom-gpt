"""Agent positioning shared by bilingual landing pages and the practical guide."""
import html

COPY={
 'ru':{
  'title':'Ваш ИИ-агент.<br>На вашем ПК.',
  'sub':'Модели. Инструменты. Результат.',
  'intro':'Freedom GPT объединяет совместимые нейросети, инструменты и память проекта. Поручайте агенту код, файлы и работу в браузере. Локальные вычисления — бесплатно, без подписки.',
  'heading':'Поручите результат.<br>Работайте с агентом.',
  'lead':'От задачи до файлов проекта: агент использует модель для рассуждений, инструменты для действий и память для продолжения работы.',
  'preview':'Обновление агента · версия 1.5.0',
  'status':'В версии 1.5.0: цели, редактируемая очередь, ветки чатов, память проекта, награды и необязательные подключения аккаунтов. Выберите сборку для своей системы ниже.',
  'cards':[
   ('01','Код и реальные файлы','Попросите создать сайт или приложение. Агент может править файлы, запускать команды и тесты через доступный терминал, объяснять изменения и возвращаться к проекту.'),
   ('02','Цель вместо одного ответа','Задайте результат и критерии готовности. Агент сверяется с целью после хода и продолжает работу. Есть пауза, история и повторная активация, если результат ещё не принят.'),
   ('03','Очередь и управление ходом','Отправляйте следующие задания во время работы, меняйте их порядок, редактируйте и удаляйте. Срочная поправка передаётся текущему заданию.'),
   ('04','Память, ветки и навыки','История и заметки проекта хранятся на диске. Создавайте ветки диалога, сохраняйте рабочие инструкции как навыки и меняйте совместимую модель в чате.'),
   ('05','Браузер и приложения','Смотрите сайт рядом с чатом. Агент может получать снимки и проверять страницу. Через установленные инструменты и скрипты доступны приложения, включая Blender для 3D.'),
   ('06','Ваш выбор моделей','Проверка ПК подсказывает варианты для кода, чата, фото и видео. Есть совместимые GGUF и необязательные подключения Hugging Face, GitHub и поддерживаемых API.')],
  'workflow':['Выберите совместимую модель','Укажите проект и цель','Следите за действиями и результатом'],
  'detail':'Как работает ИИ-агент →',
  'limits':'Возможности зависят от модели, памяти ПК, установленных программ и выданных разрешений. Blender и специализированные утилиты устанавливаются отдельно. Для анализа скриншотов нужна визуальная модель. Память не безгранична; сложные результаты требуют проверки.',
  'free':'Локальные модели работают без оплаты за токены. Сетевые функции требуют интернета; внешние API имеют собственные лимиты и тарифы.',
 },
 'en':{
  'title':'Your AI agent.<br>On your computer.',
  'sub':'Models. Tools. Results.',
  'intro':'Freedom GPT brings compatible AI models, tools and project memory together. Delegate coding, files and browser work to an agent. Local inference is free, with no subscription.',
  'heading':'Describe the outcome.<br>Work with an agent.',
  'lead':'From a task to project files: the model reasons, tools perform actions and project memory helps the agent pick up work again.',
  'preview':'Agent update · version 1.5.0',
  'status':'Version 1.5.0 brings goals, an editable queue, chat branches, project memory, rewards and optional account connections. Choose your platform below.',
  'cards':[
   ('01','Code and real project files','Ask for a website or application. With available terminal tools, the agent can edit files, run commands and tests, explain changes and return to the project.'),
   ('02','A goal beyond one reply','Define an outcome and acceptance criteria. The agent checks its goal after a turn and can continue working. Pause it, inspect history or reactivate a goal whose result you have not accepted.'),
   ('03','Queue and steering','Send follow-up tasks while work is in progress. Reorder, edit or remove queued prompts, and send an urgent correction to the current task.'),
   ('04','Memory, branches and skills','History and project notes stay on disk. Branch a conversation, save working instructions as skills and switch compatible models within a chat.'),
   ('05','Browser and applications','Inspect a website beside the chat. The agent can take snapshots and check the page. Installed tools and scripts can also drive applications, including Blender for 3D work.'),
   ('06','Your choice of models','Hardware checks suggest options for code, chat, vision and video. Use compatible GGUF files and optional Hugging Face, GitHub and supported API connections.')],
  'workflow':['Choose a compatible model','Select a project and a goal','Review actions and the result'],
  'detail':'How the AI agent works →',
  'limits':'Capabilities depend on the model, PC memory, installed software and granted permissions. Blender and specialist utilities are separate installations. Screenshot analysis needs a vision model. Memory is finite and complex results need verification.',
  'free':'Local models have no per-token charge from Freedom GPT. Online features require internet; external APIs have their own limits and pricing.',
 }
}

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

def decorate(page,lang):
 start=page.index('<section class="section wrap" id="workspace">');end=page.index('</section>',start)+len('</section>')
 page=page[:start]+gallery(lang)+page[end:]
 start=page.index('<section class="section wrap feature-section" id="features">');end=page.index('</section>',start)+len('</section>')
 page=page[:start]+section(lang)+page[end:]
 return page.replace('</head>','<link rel="stylesheet" href="/agent.css?v=20261021-panels"></head>')

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
