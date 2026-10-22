"""Current product showcase; release availability comes from the site's metadata."""
import html,json,pathlib

FEATURE_VERSION='1.6.0'
def public_version():
 return json.loads((pathlib.Path(__file__).parent/'project.json').read_text(encoding='utf-8'))['version']
def pending():
 return tuple(map(int,public_version().split('.'))) < tuple(map(int,FEATURE_VERSION.split('.')))
def availability(lang):
 v=public_version()
 if not pending():return 'Available in '+FEATURE_VERSION if lang=='en' else 'Доступно в '+FEATURE_VERSION
 return ('Preview of the upcoming '+FEATURE_VERSION+'. Current downloads: '+v+'. The features below require the new version.' if lang=='en' else 'Обзор готовящейся '+FEATURE_VERSION+'. Сейчас для скачивания доступна '+v+'. Новые функции ниже появятся в новой версии.')

def configure(text,copies):
 from agent_content import COPY
 for lang in ['ru','en']:
  en=lang=='en';d=COPY[lang]
  d['preview']=('Coming in ' if en else 'Готовим обновление ')+FEATURE_VERSION if pending() else ('New release · ' if en else 'Новый релиз · ')+FEATURE_VERSION
  d['status']=availability(lang)
  d['intro']=('A free AI agent for your computer. Build websites, work with files, create images and keep projects moving. Use a phone companion and earn achievements in the new version.' if en else 'Бесплатный ИИ-агент для вашего компьютера. Создавайте сайты, работайте с файлами, рисуйте и развивайте проекты. В новой версии — пульт с телефона и награды за результаты.')
  text[lang].update(title=d['title'],titleSub='Create. Explore. Level up.' if en else 'Создавайте. Исследуйте. Прокачивайтесь.',intro=d['intro'])
  extras=[('13','Reply notifications' if en else 'Уведомления о готовом ответе','A small card and a soft chime when a reply is ready, including other chats. Notifications and sound have separate switches on each device. Phone notifications work while the agent page is open.' if en else 'Карточка и мягкий короткий звук, когда ответ готов, в том числе в другом чате. Уведомления и звук настраиваются на каждом устройстве. На телефоне — пока открыта страница агента.'),
   ('14','Optional accounts and APIs' if en else 'Аккаунты и API по желанию','Use your GitHub account for repository workflows and Hugging Face for compatible model downloads. Local GGUF files also work without signing in. External services may charge separately.' if en else 'Подключите свой GitHub для работы с репозиториями и Hugging Face для загрузки совместимых моделей. Можно использовать локальный GGUF без входа в аккаунты. Внешние сервисы могут быть платными.'),
   ('15','Your interface' if en else 'Интерфейс под вас','Русский, English and 中文. Light and dark themes, compact settings, expandable tools and update checks at your command.' if en else 'Русский, English и 中文. Светлая и тёмная темы, компактные настройки, раскрывающиеся дополнительные инструменты и проверка обновлений по вашей команде.')]
  d['cards']=[card for card in d['cards'] if card[0] not in {'13','14','15'}]+extras
  faq=copies[lang]['faq']
  faq[:]=[(q,a) for q,a in faq if '100' not in q and q not in ['Is Freedom GPT really free?','Freedom GPT действительно бесплатный?']]
  faq[:0]=[
   ('Is it free?' if en else 'Это бесплатно?', 'Yes. Freedom GPT is free and open source, with no subscription, advertising or per-token charge for local inference. You supply hardware and download model weights separately. Third-party APIs keep their own pricing.' if en else 'Да. Freedom GPT бесплатен, с открытым кодом, без подписки, рекламы и оплаты локальных токенов. Нужен ваш компьютер; веса моделей скачиваются отдельно. У сторонних API свои тарифы.'),
   ('Can I control it from my iPhone?' if en else 'Можно управлять с iPhone?', 'The new version includes optional browser access: pair by QR code and approve on the computer. Your PC must stay on, awake and online. No App Store installation is needed. Traffic uses the project relay, which has capacity limits.' if en else 'В новой версии есть необязательный доступ через браузер: QR-код и подтверждение на компьютере. ПК должен работать, не спать и иметь интернет. Приложение из App Store не требуется. Связь идёт через сервер проекта с ограничениями нагрузки.'),
   ('Are Freedom points cryptocurrency?' if en else 'Игровые Freedom — это криптовалюта?', 'No. They are local game points and achievements. They cannot currently be transferred, sold or exchanged, and carry no promise of future value or conversion.' if en else 'Пока это локальные игровые баллы и достижения. Сейчас их нельзя переводить, продавать или обменивать. Будущая стоимость или конвертация не обещается.'),
   ('Will it work on my PC?' if en else 'Подойдёт ли мой компьютер?', 'The app checks CPU, RAM, GPU and storage, then suggests compatible models. A smaller model needs less memory. Actual speed and quality depend on your hardware, model and context size.' if en else 'Программа проверяет CPU, RAM, GPU и место на диске и предлагает модели. Небольшие модели требуют меньше памяти. Реальная скорость и качество зависят от вашего железа, модели и размера контекста.')]

def highlights(lang):
 en=lang=='en'
 rows=[('01','Your PC does the work' if en else 'Ваш ПК делает работу','Files, code, websites and creative tasks in one agent workspace.' if en else 'Файлы, код, сайты и творчество в одном рабочем пространстве.','#features'),
       ('02','Your phone stays connected' if en else 'Телефон держит в курсе','Watch progress and send the next task while your computer keeps running.' if en else 'Смотрите прогресс и ставьте задачи, пока компьютер продолжает работать.','#phone'),
       ('03','Your results become progress' if en else 'Результаты становятся прогрессом','Achievements, XP, ranks and a personal Freedom game balance.' if en else 'Достижения, опыт, ранги и личный игровой баланс Freedom.','#rewards')]
 cards=''.join('<a href="'+url+'"><small>'+n+'</small><h3>'+html.escape(title)+'</h3><p>'+html.escape(body)+'</p><span aria-hidden="true">↗</span></a>' for n,title,body,url in rows)
 src='/media/screenshots/workspace-160-'+lang+'.png'
 caption='Real Windows 1.6.0 preview. Your workspace starts with a clean slate.' if en else 'Настоящая Windows-сборка 1.6.0. Ваше рабочее пространство начинается с чистого листа.'
 shot='<figure class="wrap showcase-workspace"><a href="'+src+'" target="_blank" rel="noopener"><img src="'+src+'" alt="'+html.escape(caption)+'" width="1280" height="720" loading="lazy"></a><figcaption>'+html.escape(caption)+'</figcaption></figure>'
 return '<section class="wrap showcase-highlights" aria-label="'+('Why Freedom GPT' if en else 'Зачем вам Freedom GPT')+'">'+cards+'</section>'+shot

def rewards(lang):
 en=lang=='en';e=html.escape
 title='Level up your<br>real-world skills.' if en else 'Прокачивайте навыки.<br>Создавайте по-настоящему.'
 lead='A first website. A first image. A million model tokens. Freedom keeps your milestones in a creator profile with XP, ranks and a constellation of skills.' if en else 'Первый сайт. Первая картинка. Миллион токенов модели. Freedom собирает этапы вашего пути в профиль создателя: опыт, ранги и созвездие навыков.'
 points=['Websites, apps, code, images and video','Games, research, SEO, analysis and authorized security work','New confirmed results keep adding to your counters','Automatic activity tracking plus confirmation for completed work'] if en else ['Сайты, приложения, код, изображения и видео','Игры, исследования, SEO, аналитика и разрешённые аудиты','Каждый новый подтверждённый результат пополняет счётчик','Автоматический учёт активности и подтверждение готовых работ']
 note='Freedom is a local game balance, not cryptocurrency. There are no transfers, exchange or promised earnings. Progress stays on your PC and can be exported.' if en else 'Freedom — локальный игровой баланс. Сейчас это не криптовалюта: переводов, обмена и обещаний дохода нет. Прогресс хранится на вашем ПК, его можно экспортировать.'
 return '<section class="section wrap showcase-rewards" id="rewards"><div><div class="eyebrow">FREEDOM GPT / CREATOR PROGRESSION</div><h2>'+title+'</h2><p>'+e(lead)+'</p><ul>'+''.join('<li>'+e(x)+'</li>' for x in points)+'</ul><small class="showcase-availability">'+e(availability(lang))+'</small></div><figure><a href="/media/screenshots/rewards-160.png" target="_blank" rel="noopener"><img src="/media/screenshots/rewards-160.png" alt="'+('Real Freedom GPT creator profile, Windows 1.6.0 preview' if en else 'Настоящий профиль создателя Freedom GPT, Windows 1.6.0')+'" loading="lazy" width="1280" height="720"></a><figcaption>'+e(note)+'</figcaption></figure></section>'

def decorate(page,lang):
 en=lang=='en'
 if pending():
  from agent_content import COPY
  intro=COPY[lang]['intro']
  note=('1.6.0 preview · current download '+public_version()) if en else ('Обзор 1.6.0 · сейчас скачивается '+public_version())
  page=page.replace(intro,intro+'<small class="showcase-hero-status">'+html.escape(note)+'</small>',1)
 marker='<section class="section wrap panel-gallery" id="workspace">'
 page=page.replace(marker,highlights(lang)+marker,1)
 marker='<section class="section wrap phone-feature"'
 page=page.replace(marker,rewards(lang)+marker,1)
 label='Phone' if en else 'Телефон';reward='Achievements' if en else 'Награды'
 page=page.replace('</nav><div class="header-actions">',f'<a href="#phone">{label}</a><a href="#rewards">{reward}</a></nav><div class="header-actions">',1)
 return page
