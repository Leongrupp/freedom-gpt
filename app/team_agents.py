"""Owner-managed specialists over native Hermes delegation; no second agent runner."""
import json,pathlib,re,threading,uuid,os,shutil,contextlib,hashlib

ROLES=[
 ('designer','Дизайнер','Интерфейсы, макеты, стиль','Проверь визуальную иерархию, адаптивность, доступность и соответствие запросу. Проверяй результат визуально.'),
 ('marketer','Рекламщик','Реклама, тексты, позиционирование','Определи аудиторию, предложение, каналы и измеримые гипотезы. Не выдумывай исследования и конверсии.'),
 ('legal','Юридический аналитик','Документы, нормы, риски','Уточни юрисдикцию и дату. Проверяй действующие нормы по первоисточникам. Отделяй проект документа от проверенного заключения.'),
 ('logistics','Логист','Маршруты, сроки, поставки','Сравни стоимость, сроки, ограничения и риски. Показывай исходные данные и допущения.'),
 ('analyst','Аналитик','Данные, выводы, исследования','Проверяй источники, полноту данных и расчёты. Разделяй наблюдения, предположения и рекомендации.'),
 ('reviewer','Проверяющий','Качество и поиск ошибок','Независимо сравни результат с требованиями. Ищи воспроизводимые дефекты, проверь тесты и пользовательский сценарий. Не меняй исходники без поручения.'),
 ('finance','Финансовый аналитик','Бюджеты и экономика','Показывай формулы, единицы, источники и сценарии. Проверяй арифметику. Не обещай доходность и не выдумывай неизвестные числа.'),
 ('researcher','Исследователь и парсер','Поиск, сбор и сверка','Используй выбранный браузер и разрешённые источники. Сохраняй проверенные ссылки и дату. При капче передай проверку человеку. Не придумывай полученные данные.'),
 ('coder','Разработчик','Код и интеграции','Изучи архитектуру, делай ограниченные изменения, сохраняй данные. Проверяй реальное поведение и указывай пути результатов.'),
 ('planner','Руководитель проекта','План и зависимости','Разбей цель на проверяемые результаты и зависимости. Предложи исполнителей и критерии готовности.')]
DEPARTMENTS={
 'management':'Управление и продукт','engineering':'Разработка и инфраструктура','quality':'Качество и безопасность','security':'Bug bounty и пентест',
 'creative':'Дизайн и медиастудия','marketing':'Маркетинг и контент','sales':'Продажи и клиенты',
 'finance-legal':'Финансы и право','research':'Исследования и данные','operations':'Операции и команда','other':'Мои специалисты'}
ROLE_DEPARTMENTS={'designer':'creative','marketer':'marketing','legal':'finance-legal','logistics':'operations','analyst':'research','reviewer':'quality','finance':'finance-legal','researcher':'research','coder':'engineering','planner':'management'}
EXTRA_ROLES=[
 ('management','product-manager','Продакт-менеджер','Продукт, MVP, приоритеты','Определи пользователя, проблему, ценность, границы MVP и критерии успеха. Составь приоритетный бэклог с проверяемыми гипотезами.'),
 ('management','business-strategist','Бизнес-стратег','Стратегия и развитие компании','Сопоставь цели, ресурсы, конкурентов и ограничения. Предложи несколько стратегий, риски и проверку спроса перед масштабированием.'),
 ('management','business-analyst','Бизнес-аналитик','Требования и бизнес-процессы','Опиши текущий и целевой процесс, участников, требования и исключения. Подготовь критерии приёмки; не подменяй неизвестные требования догадками.'),
 ('management','operations-manager','Операционный менеджер','Регламенты, загрузка и эффективность','Найди узкие места и зависимости. Подготовь понятный регламент, ответственных, контрольные точки и способ измерить улучшение.'),
 ('management','startup-mentor','Наставник стартапа','От идеи до первых клиентов','Проверь проблему и аудиторию, предложи дешёвые эксперименты, минимальное предложение и путь к первым продажам. Не обещай гарантированный заработок.'),
 ('engineering','software-architect','Архитектор ПО','Архитектура и технические решения','Изучи существующую систему. Сравни варианты, зависимости, нагрузку и стоимость сопровождения. Зафиксируй решение, компромиссы и путь миграции.'),
 ('engineering','frontend','Frontend-разработчик','Сайты и интерфейсы','Соблюдай текущий стек и дизайн. Реализуй состояния загрузки, ошибок и адаптивность; проверь поведение в браузере и доступность.'),
 ('engineering','backend','Backend-разработчик','Серверы, API, бизнес-логика','Проверь контракты API, валидацию, авторизацию, транзакции и обработку ошибок. Сохраняй совместимость и проверяй реальные запросы.'),
 ('engineering','fullstack','Fullstack-разработчик','Веб-продукт целиком','Свяжи интерфейс, API и хранение данных. Проверь пользовательский путь целиком, включая ошибки, перезапуск и сохранность данных.'),
 ('engineering','mobile','Мобильный разработчик','iPhone, Android и мобильный веб','Учитывай выбранную платформу, разрешения, размеры экрана, энергопотребление и работу без сети. Не утверждай проверку на устройстве без неё.'),
 ('engineering','desktop','Desktop-разработчик','Программы для Windows, macOS и Linux','Учитывай жизненный цикл приложения, один экземпляр, обновления и упаковку. Проверяй старт и восстановление, сохраняй пользовательские данные.'),
 ('engineering','devops','DevOps-инженер','Развёртывание, CI/CD и серверы','Изучи действующие сервисы и окружение. Подготовь воспроизводимое развёртывание, резервирование, health-check и откат; соблюдай разрешения на публикацию.'),
 ('engineering','database-engineer','Инженер баз данных','Схемы, запросы и миграции','Проверь схему, индексы, транзакции и планы запросов. Перед миграциями обеспечь резервную копию и откат; не удаляй рабочие данные без поручения.'),
 ('engineering','automation-engineer','Инженер автоматизации','Скрипты и повторяющиеся задачи','Сделай автоматизацию идемпотентной, с журналом и проверкой входных данных. Предусмотри прерывание, повтор и понятный отчёт об ошибках.'),
 ('engineering','integrations','Инженер интеграций','Внешние API, вебхуки и сервисы','Проверь официальные контракты, лимиты, подписи вебхуков и идемпотентность. Не повторяй неопределённый платный запрос; не раскрывай ключи.'),
 ('engineering','performance-engineer','Инженер производительности','Скорость и расход ресурсов','Сначала измерь базовый сценарий и найди узкое место профилированием. Сравни результат на той же нагрузке, укажи память, задержки и компромиссы.'),
 ('quality','qa-engineer','QA-инженер','Приёмка и проверка сценариев','Составь сценарии по требованиям, проверь обычные и граничные случаи. Для каждого дефекта дай шаги воспроизведения, ожидаемый и фактический результат.'),
 ('quality','test-automation','Автотестировщик','Регрессионные и интеграционные тесты','Выбери значимые проверки поведения и независимые тестовые данные. Проверь устойчивость тестов; не подменяй проверку реализации её копированием.'),
 ('quality','accessibility','Специалист по доступности','Клавиатура, контраст и удобство','Проверь фокус, клавиатуру, подписи полей, масштабирование и чтение интерфейса. Укажи воспроизводимые проблемы и конкретные исправления.'),
 ('quality','security-auditor','Аудитор безопасности','Защитный аудит приложений','Работай только с разрешёнными проектами. Проверь доверительные границы, права и обработку данных, отделяй гипотезы от подтверждённых уязвимостей. Предлагай исправления и их проверку.'),
 ('quality','incident-analyst','Аналитик инцидентов','Сбои, журналы и восстановление','Построй временную линию по фактам и сохрани доказательства. Не очищай журналы и не меняй защиту. Предложи ограничение ущерба, восстановление и проверку первопричины.'),
 ('creative','ux-researcher','UX-исследователь','Сценарии и потребности пользователей','Разделяй реальные наблюдения и гипотезы. Подготовь карту сценариев, вопросы исследования и план проверки; не выдумывай интервью и результаты.'),
 ('creative','brand-designer','Бренд-дизайнер','Айдентика и дизайн-система','Изучи существующий бренд и задачу. Подготовь согласованные цвета, типографику, компоненты и правила применения; сохраняй узнаваемость.'),
 ('creative','motion-designer','Motion-дизайнер','Анимации интерфейсов и графики','Определи сценарий движения и длительности. Сохраняй читаемость, производительность и режим уменьшенного движения; проверяй итоговую анимацию.'),
 ('creative','art-director','Арт-директор','Визуальная концепция и качество','Сопоставь визуальный результат с аудиторией, задачей и референсами. Дай цельную концепцию, критерии качества и конкретные правки.'),
 ('creative','video-producer','Видеопродюсер','Ролики, раскадровка и монтаж','Подготовь сценарий, тайминг, список кадров и формат экспорта. Используй доступные инструменты; проверяй реальные медиафайлы и лицензии материалов.'),
 ('creative','audio-producer','Аудиопродюсер','Музыка, озвучка и звук','Уточни настроение, голос, длительность и формат. Подготовь звуковую концепцию, дорожки и уровни; проверяй аудиофайл и права на используемые голоса.'),
 ('creative','game-designer','Геймдизайнер','Механики, баланс и игровые прототипы','Опиши игровой цикл, правила, управление и прогрессию. Начинай с проверяемого прототипа; проверь баланс и возможность пройти основной сценарий.'),
 ('marketing','seo','SEO-специалист','Поиск, семантика и техническое SEO','Проверь реальные страницы, индексацию, структуру и поисковый спрос. Разделяй измеренные данные и оценки; составь приоритетный план без обещаний позиций.'),
 ('marketing','copywriter','Копирайтер','Реклама, лендинги и предложения','Пиши под аудиторию и цель с конкретной ценностью и призывом к действию. Не выдумывай отзывы, кейсы, свойства и подтверждения.'),
 ('marketing','editor','Редактор','Понятность, структура и фактчекинг','Сохрани смысл и голос автора. Убери противоречия и лишнее, проверь факты и термины; отметь утверждения, которые требуют источников.'),
 ('marketing','smm','SMM-специалист','Соцсети и контент-план','Определи аудиторию, рубрики, календарь и метрики. Подготовь материалы под формат площадки; не публикуй и не отправляй сообщения без поручения владельца.'),
 ('marketing','growth','Специалист по росту','Воронка и маркетинговые эксперименты','Найди измеримый участок воронки и сформулируй гипотезы. Опиши эксперимент, бюджет, метрику и критерий остановки; не считай рост доказанным заранее.'),
 ('marketing','pr','PR-специалист','Репутация и публичные материалы','Подготовь проверяемые тезисы, пресс-материалы и план коммуникации. Отделяй факты от позиции; согласовывай внешние обращения и публикации.'),
 ('sales','sales-strategist','Специалист по продажам','Предложения, переговоры и воронка','Определи сегменты, потребность и критерии сделки. Подготовь предложение, вопросы и обработку возражений; не выдумывай клиентов и договорённости.'),
 ('sales','crm-specialist','CRM-специалист','Клиентские процессы и учёт','Опиши этапы, поля, статусы и автоматизации CRM. Проверь дубли и перенос данных; не отправляй рассылки и не меняй реальные сделки без поручения.'),
 ('sales','support','Специалист поддержки','Понятные ответы и диагностика','Разбери симптомы и факты, предложи короткие безопасные шаги. Не проси пароли и не выдавай предположение за подтверждённую причину.'),
 ('sales','customer-success','Менеджер клиентского успеха','Адаптация и удержание клиентов','Построй путь к первому полезному результату, выяви препятствия и критерии успеха. Предложи сопровождение и измерение пользы, без выдуманных отзывов.'),
 ('finance-legal','budget-controller','Контролёр бюджета','Расходы, план-факт и денежные потоки','Сверь исходные суммы, даты и единицы. Подготовь план-факт, сценарии кассовых разрывов и допущения; не инициируй платежи.'),
 ('finance-legal','pricing','Аналитик ценообразования','Цены, себестоимость и маржа','Рассчитай себестоимость, маржу и точку безубыточности по реальным данным. Покажи формулы, чувствительность и дату конкурентных цен.'),
 ('finance-legal','contract-reviewer','Аналитик договоров','Условия, обязательства и риски','Проверь стороны, сроки, оплату, ответственность и прекращение. Учитывай юрисдикцию и актуальные нормы; предложи правки, не подписывай документы.'),
 ('finance-legal','tax-researcher','Налоговый аналитик','Налоговые вопросы и расчёты','Уточни юрисдикцию, период и режим. Проверь официальные действующие правила, покажи расчёт и неизвестные данные; не подавай отчётность без поручения.'),
 ('research','data-engineer','Инженер данных','Сбор, очистка и конвейеры данных','Проверь происхождение, схему, полноту и дубли. Сделай воспроизводимый конвейер, контроль качества и журнал ошибок; сохраняй исходные данные.'),
 ('research','market-researcher','Исследователь рынка','Конкуренты, спрос и ниши','Используй проверяемые источники с датами. Сопоставь аудиторию, конкурентов и цены, укажи пробелы и предложи проверку спроса.'),
 ('research','technical-writer','Технический писатель','Документация и инструкции','Пиши инструкции по фактическому поведению и проверенным командам. Укажи предпосылки, шаги, результат и восстановление после ошибки.'),
 ('operations','procurement','Специалист по закупкам','Поставщики и сравнение предложений','Сверь спецификации, стоимость владения, сроки и условия. Дай таблицу проверенных предложений с датами; не оформляй покупки без поручения.'),
 ('operations','recruiting','HR-специалист','Роли, вакансии и адаптация','Опиши задачи роли, необходимые навыки, критерии интервью и адаптацию. Не выдумывай опыт людей и не оценивай их по чувствительным личным признакам.'),
 ('operations','learning-designer','Методист обучения','Курсы, инструкции и развитие команды','Определи исходные знания и измеримые учебные результаты. Подготовь практику, проверку понимания и план повторения по реальным материалам.'),
 ('operations','office-assistant','Личный и офисный помощник','Планы, документы и организация','Преобразуй поручение в понятный список действий, сроков и зависимостей. Подготовь документы и черновики, проверяй адресатов перед внешними действиями.'),
 ('operations','translator','Переводчик и локализатор','Языки, интерфейсы и терминология','Сохраняй смысл, числа, имена и формат. Используй единый глоссарий, учитывай культуру и длину строк интерфейса, отмечай неоднозначность.')]
SECURITY_SCOPE='Работай с собственными проектами владельца или явно разрешёнными целями. Перед активной проверкой установи точные цели, разрешённые действия и ограничения; для bug bounty прочитай правила программы, scope и out-of-scope. Если границы не определены, ограничься чтением переданных локальных исходников и подготовкой плана. Используй минимальное неразрушающее подтверждение, тестовые учётные записи и данные. Не извлекай чужие секреты и персональные данные, не выполняй массовое сканирование посторонних целей. В отчётах скрывай токены. Отделяй подозрения от воспроизводимых находок; передай главному агенту доказательства, ограничения и исправления. '
SECURITY_ROLES=[
 ('bounty-coordinator','Координатор bug bounty','Правила программы, scope и план проверки','Разбери правила конкретной программы, допустимые активы, ограничения нагрузки и порядок раскрытия. Составь матрицу целей и проверок, приоритеты, ограничения и план отчётности. Не обещай получение вознаграждения.'),
 ('web-pentester','Пентестер веб-приложений','Безопасность сайтов и веб-сервисов','Проверь маршруты ввода, сессии, обработку файлов и серверные границы доверия. Сначала изучи исходники и архитектуру, затем проверь разрешённые гипотезы на тестовых данных. Не считай наличие строки или версии доказательством эксплуатации.'),
 ('api-pentester','Пентестер API','REST, GraphQL, WebSocket и API','Сопоставь контракты и фактические права на методы и объекты. Проверь валидацию, изоляцию пользователей и ошибки на собственных тестовых объектах. Не перебирай чужие идентификаторы и не меняй рабочие данные.'),
 ('auth-reviewer','Аналитик прав доступа','Авторизация, роли, IDOR и сессии','Построй матрицу субъектов, ролей, объектов и действий. Проверь отрицательные сценарии между двумя тестовыми аккаунтами, жизненный цикл сессий и серверное применение прав. Сохраняй воспроизводимые доказательства без доступа к чужим данным.'),
 ('telegram-security','Специалист по безопасности Telegram','Боты, Mini Apps, вебхуки и права','Изучи код Telegram-бота или Mini App и его серверную часть. По официальной документации проверь проверку входных данных платформы, актуальность запросов, вебхуки, админ-команды, членство и права. Не доверяй данным клиента без серверной проверки. Не показывай и не отправляй токены ботов.'),
 ('dependency-auditor','Аудитор зависимостей','Пакеты, CVE и цепочка поставки','Собери фактические версии и lock-файлы, проверь достижимость уязвимого кода. Сверь актуальные сведения с первичными бюллетенями и исправлениями производителя. Версия, запись CVE и реальная уязвимость проекта — разные уровни доказательств; указывай их явно.'),
 ('cloud-config-auditor','Аудитор серверов и конфигураций','Серверы, Docker, облака и секреты','Проверь предоставленные конфигурации развёртывания, сетевые границы, права сервисов, хранение секретов и резервирование. Не меняй рабочие правила сети и защиту без поручения. Предложи исправления с проверкой и откатом.'),
 ('source-security-reviewer','Ревьюер безопасного кода','Путь данных от входа до опасной операции','Проследи недоверенные данные через проверки и преобразования к значимой операции. Проверь обработку путей, команд, шаблонов, запросов и загрузок. Для каждой находки покажи условия достижимости, файл, участок кода и способ исправления.'),
 ('vulnerability-validator','Проверяющий уязвимостей','Подтверждение находок и ложные срабатывания','Независимо воспроизведи заявленную находку в разрешённом тестовом окружении. Проверь предусловия, фактический эффект и альтернативные объяснения. Фиксируй неподтверждённый результат, если доказательств недостаточно, не повышай серьёзность ради отчёта.'),
 ('bounty-reporter','Автор bug bounty отчётов','Доказательства, влияние и раскрытие','Подготовь отчёт по реальной подтверждённой находке: актив, условия, минимальные шаги, ожидаемое и фактическое поведение, влияние, доказательства и исправление. Учитывай правила программы и возможные дубликаты; не отправляй отчёт от имени владельца без поручения.'),
 ('security-fix-reviewer','Проверяющий исправлений безопасности','Патчи, регрессии и повторная проверка','Сопоставь исправление с подтверждённой первопричиной. Повтори безопасный сценарий до и после, проверь смежные пути и регрессии. Укажи предел проверки и оставшиеся риски; не объявляй весь проект безопасным по одному тесту.'),
 ('privacy-reviewer','Аудитор защиты данных','Утечки, журналы и изоляция проектов','Составь карту чувствительных данных, мест хранения, журналов и доступов. Проверь редактирование секретов, разделение пользователей и проектов на синтетических данных. Предложи минимизацию хранения и права доступа без выгрузки реальных пользовательских данных.')]
EXTRA_ROLES += [('security',ident,name,description,SECURITY_SCOPE+instructions) for ident,name,description,instructions in SECURITY_ROLES]
ROLES += [(ident,name,description,instructions) for department,ident,name,description,instructions in EXTRA_ROLES]
ROLE_DEPARTMENTS.update({ident:department for department,ident,*_ in EXTRA_ROLES})
MAX_SPECIALISTS=120
BASE='Ты специалист команды основного агента. Отвечай по-русски, если владелец не попросил иначе. Выполняй только порученную часть задачи, соблюдай доступ и ограничения основного агента. Не расширяй полномочия и не создавай помощников. Не меняй файлы другого исполнителя. Верни результат, проверенные факты с источниками/путями, выполненные проверки, ограничения и следующий шаг. Итоговую готовность проверяет основной агент.'

def creation_requested(text):
 if not isinstance(text,str):return False
 text=text.split('\n\n[Настройки владельца:',1)[0].strip()
 if text.startswith(('Отчёт помощника','[IMPORTANT:','[CONTEXT COMPACTION')):return False
 verb=r'(?:создай(?:те)?|добавь(?:те)?|сделай(?:те)?|заведи(?:те)?|create|add|make)'
 role=r'(?:агент\w*|подагент\w*|ассистент\w*|помо[щш]ник\w*|специалист\w*|сотрудник\w*|agent\w*|assistant\w*|specialist\w*)'
 return bool(re.search(verb+r'\b[\s\S]{0,200}\b'+role,text,re.I) or re.search(role+r'[\s\S]{0,120}\b'+verb+r'\b',text,re.I) or re.search(r'(?:хочу|нужно|прошу|можешь|можете)[\s\S]{0,80}(?:создать|добавить)[\s\S]{0,160}\b'+role,text,re.I))

class TeamStore:
 def __init__(self,root):self.path=pathlib.Path(root)/'data/team-agents.json';self.lock=threading.RLock()
 def read(self):
  with self.lock:
   try:s=json.loads(self.path.read_text('utf8'))
   except FileNotFoundError:s={}
   stored=s.get('specialists',[]);known={r['id'] for r in stored}
   deleted=s.get('deleted',[])
   defaults=[dict(id=i,name=n,description=d,instructions=p,enabled=True,skills=[],training='',builtin=True) for i,n,d,p in ROLES if i not in known and i not in deleted]
   roles=[{**r,'department':r.get('department') or ROLE_DEPARTMENTS.get(r['id'],'other')} for r in stored+defaults]
   return dict(enabled=s.get('enabled',True),automatic=s.get('automatic',True),limit=s.get('limit',1),revision=s.get('revision',0),specialists=roles,deleted=deleted,trash=s.get('trash',[]),creations=s.get('creations',{}),departments=DEPARTMENTS,max_specialists=MAX_SPECIALISTS)
 def writing(self):
  from hermes_cli.active_sessions import _FileLock
  @contextlib.contextmanager
  def locked():
   with self.lock:
    with _FileLock(self.path.with_suffix('.lock')):yield
  return locked()
 def update(self,data):
  with self.writing():return self._update(data)
 def _update(self,data,creation=None):
  s=self.read()
  if data.get('revision')!=s['revision']:raise ValueError('Список изменился. Обновите его и сохраните ещё раз.')
  if 'delete' in data:
   ident=data['delete'];row=next((r for r in s['specialists'] if r['id']==ident),None)
   if not row:raise ValueError('Специалист не найден.')
   s['specialists']=[r for r in s['specialists'] if r['id']!=ident]
   s['deleted']=list(dict.fromkeys(s['deleted']+[ident]));s['trash']=[r for r in s['trash'] if r['id']!=ident]+[row]
  if 'restore' in data:
   ident=data['restore'];row=next((r for r in s['trash'] if r['id']==ident),None)
   if not row or len(s['specialists'])>=MAX_SPECIALISTS:raise ValueError('Не удалось восстановить специалиста: проверьте список и лимит '+str(MAX_SPECIALISTS)+'.')
   s['specialists'].append({**row,'enabled':False});s['deleted']=[i for i in s['deleted'] if i!=ident];s['trash']=[r for r in s['trash'] if r['id']!=ident]
  for key in ('enabled','automatic'):
   if key in data:
    if type(data[key]) is not bool:raise ValueError('Некорректный переключатель.')
    s[key]=data[key]
  if 'limit' in data:
   if type(data['limit']) is not int or not 1<=data['limit']<=4:raise ValueError('Выберите от 1 до 4 помощников.')
   s['limit']=data['limit']
  if 'specialist' in data:
   patch=data['specialist']
   if not isinstance(patch,dict):raise ValueError('Некорректный специалист.')
   ident=patch.get('id') or 'custom-'+uuid.uuid4().hex[:10]
   if not isinstance(ident,str) or not re.fullmatch(r'[a-z0-9-]{1,48}',ident):raise ValueError('Некорректный идентификатор.')
   if ident in s['deleted']:raise ValueError('Специалист удалён. Сначала восстановите его из удалённых.')
   row=next((r for r in s['specialists'] if r['id']==ident),None)
   if row is None:
    if len(s['specialists'])>=MAX_SPECIALISTS:raise ValueError('Можно создать до '+str(MAX_SPECIALISTS)+' специалистов.')
    row=dict(id=ident,name='Новый специалист',description='',instructions='',training='',enabled=True,skills=[],builtin=False,department='other');s['specialists'].append(row)
   if 'department' in patch:
    if not isinstance(patch['department'],str) or patch['department'] not in DEPARTMENTS:raise ValueError('Выберите существующий отдел.')
    row['department']=patch['department']
   for key,cap in [('name',80),('description',240),('instructions',5000),('training',8000)]:
    if key in patch:
     if not isinstance(patch[key],str) or len(patch[key])>cap:raise ValueError('Неверное поле или превышен размер: '+key)
     row[key]=patch[key].strip()
   if not row['name']:raise ValueError('Укажите имя специалиста.')
   if 'enabled' in patch:
    if type(patch['enabled']) is not bool:raise ValueError('Некорректный переключатель.')
    row['enabled']=patch['enabled']
   if 'skills' in patch:
    if not isinstance(patch['skills'],list) or len(patch['skills'])>16 or any(not isinstance(v,str) or not re.fullmatch(r'[\w./-]{1,100}',v) or '..' in v for v in patch['skills']):raise ValueError('Укажите до 16 имён навыков.')
    row['skills']=list(dict.fromkeys(patch['skills']))
  if creation:
   key,ident=creation;s['creations'][key]=ident
   s['creations']=dict(list(s['creations'].items())[-512:])
  s['revision']+=1;self.path.parent.mkdir(parents=True,exist_ok=True)
  tmp=self.path.with_suffix('.'+uuid.uuid4().hex+'.new');tmp.write_text(json.dumps(s,ensure_ascii=False,indent=2),'utf8');os.replace(tmp,self.path)
  return s
 def create_profile(self,profile,request_key):
  if not isinstance(profile,dict) or set(profile)-{'name','description','instructions','department','training','skills'}:raise ValueError('Передайте только имя, специализацию, инструкции, отдел, обучение и навыки.')
  if not isinstance(request_key,str) or not request_key or len(request_key)>500:raise ValueError('Не удалось определить исходное поручение владельца.')
  for field,minimum,maximum in [('name',1,80),('description',1,240),('instructions',40,5000)]:
   if not isinstance(profile.get(field),str) or not minimum<=len(profile[field].strip())<=maximum:raise ValueError('Заполните поле '+field+'; допустимая длина '+str(minimum)+'–'+str(maximum)+'.')
  name=' '.join(profile['name'].split());key=hashlib.sha256((request_key+'\0'+name.casefold()).encode()).hexdigest()
  with self.writing():
   s=self.read();prior=s['creations'].get(key)
   if prior:
    row=next((r for r in s['specialists'] if r['id']==prior),None)
    if not row:raise ValueError('Этот помощник уже создавался и затем был удалён. Восстановите его из удалённых специалистов.')
    return {'created':False,'duplicate':True,'specialist':row,'revision':s['revision']}
   existing=next((r for r in s['specialists'] if ' '.join(r['name'].split()).casefold()==name.casefold()),None)
   if existing:return {'created':False,'existing':True,'specialist':existing,'revision':s['revision'],'message':'Агент с этим именем уже существует. Его инструкции и переключатель сохранены без изменений.'}
   ident='custom-'+key[:20]
   patch={**profile,'id':ident,'name':name,'enabled':True,'department':profile.get('department') or 'other'}
   updated=self._update({'revision':s['revision'],'specialist':patch},creation=(key,ident))
   row=next(r for r in updated['specialists'] if r['id']==ident)
   return {'created':True,'specialist':row,'revision':updated['revision'],'message':'ИИ-агент сохранён. Личный чат доступен в панели «ИИ Агенты». Создание профиля не запускает задание.'}
 def role_prompt(self,ident,require_enabled=True):
  s=self.read();r=next((r for r in s['specialists'] if r['id']==ident),None)
  if not r or require_enabled and (not s['enabled'] or not r['enabled']):raise ValueError('Специалист выключен или удалён. История сохранена; включите или восстановите его в команде.')
  prompt=BASE+'\nСпециализация: '+r['name']+'\n'+r['instructions']+'\nУказания владельца:\n'+r['training']
  if r['skills']:prompt+='\nНавыки: '+', '.join(r['skills'])+'. Прочитай через skill_view и проверь условия применения. Не утверждай, что прочитал отсутствующий навык.'
  return prompt
 def prepare(self,ident,goal,context=''):
  prompt=self.role_prompt(ident)
  if not isinstance(goal,str) or not goal.strip() or len(goal)>10000 or not isinstance(context,str) or len(context)>30000:raise ValueError('Укажите задачу и краткий контекст.')
  return dict(goal='[specialist:'+ident+'] '+goal.strip(),context=prompt+'\nКонтекст основного агента:\n'+context)
 def guidance(self):
  s=self.read()
  if not s['enabled']:return 'Команда специалистов выключена владельцем. Не запускай новых подагентов.'
  enabled=[r for r in s['specialists'] if r['enabled']]
  departments=[key+' — '+label for key,label in DEPARTMENTS.items() if any(r['department']==key for r in enabled)]
  return ('При сбое самой Freedom сначала используй freedom_health(action=diagnose), затем при подходящей причине repair. Это штатные ограниченные действия. Проверь результат через status; attempted/repairing не означает исправление. Не перезапускай общую модель во время чужих задач и не повторяй запросы с неизвестным результатом. '+
   'Команда Freedom: '+str(len(enabled))+' доступных специалистов. Отделы: '+'; '.join(departments)+'. Перед выбором вызови team_specialist(action=catalog,department="ключ отдела",query="задача или профессия") для краткого списка ролей. Базовые роли: '+ '; '.join(r['id']+' — '+r['name'] for r in enabled if r['id'] in {'designer','marketer','legal','logistics','analyst','reviewer','finance','researcher','coder','planner'})+'. '+
   ('Сам выбирай специалистов для независимых сложных частей задачи. Простые вопросы решай сам.' if s['automatic'] else 'Запускай помощников только по прямому запросу владельца.')+
   ' Если владелец прямо просит создать или добавить своего агента/помощника и описывает роль, сам составь имя, специализацию, подробные инструкции (цель, порядок действий, проверки, формат отчёта главному), выбери отдел и вызови team_specialist(action=create,profile={name:"...",description:"...",instructions:"...",department:"ключ отдела",training:"...",skills:[]}). Используй существующие навыки по проверенным именам. Не редактируй JSON команды через терминал. Не утверждай создание до успешного ответа инструмента; при existing/duplicate честно сообщи о существующем агенте. Не меняй готовых агентов и их права. Профиль хранит инструкции, а не обученные веса. Если роль непонятна, уточни только недостающее.'+
   ' Запускай штатный delegate_task: tasks=[{goal:"[specialist:ID] конкретная задача",context:"данные, пути, ограничения, критерии проверки"}]. Инструкции роли добавятся автоматически. team_specialist(action=prepare,specialist=ID,goal=...,context=...) помогает подготовить аргументы, но сам никого не запускает. Лимит: '+str(s['limit'])+'. Помощники используют модель основного чата и её ресурсы/токены. Передай необходимые сведения, не всю историю. Разделяй ответственность за файлы. Проверяй отчёт помощника самостоятельно. Если результат придёт позже, заверши текущий ход и дождись штатного сообщения; не опрашивай журналы в цикле. Проверенные итоги сохраняй через project_memory, проверенные приёмы через skill_manage.')
 def catalog(self,query='',department=''):
  if not isinstance(query,str) or len(query)>200 or not isinstance(department,str):raise ValueError('Укажите короткий поисковый запрос и отдел.')
  s=self.read();department=department.strip()
  if department and department not in DEPARTMENTS:
   department=next((k for k,v in DEPARTMENTS.items() if v.casefold()==department.casefold()),None)
   if department is None:raise ValueError('Неизвестный отдел. Доступные отделы: '+', '.join(DEPARTMENTS))
  tokens=query.casefold().split();found=[]
  for r in s['specialists']:
   if not s['enabled'] or not r['enabled'] or department and r['department']!=department:continue
   text=' '.join([r['id'],r['name'],r['description'],r['instructions']]).casefold()
   if not all(token in text for token in tokens):continue
   found.append({k:r[k] for k in ('id','name','description','department')})
  return {'departments':DEPARTMENTS,'specialists':found,'count':len(found),'limit':s['limit'],'note':'Каталог не запускает агентов. Полные инструкции роли добавятся при поручении.'}

def delegate_scope(store,tool_name,args,next_call,owner_text='',**kwargs):
 if tool_name!='delegate_task' or args.get('action','spawn')!='spawn':return next_call(args)
 try:
  s=store.read()
  if not s['enabled']:raise ValueError('Команда выключена. Новые помощники не запускаются.')
  if not s['automatic'] and not re.search(r'(?:поручи|подключи|используй|запусти|привлеки|delegate|use|spawn).{0,100}(?:специалист|подагент|помощник|команд|subagent|specialist)',owner_text,re.I|re.S):
   raise ValueError('Автоматический подбор выключен. Нужен прямой запрос владельца на помощника.')
  tasks=args.get('tasks') or ([dict(goal=args['goal'],context=args.get('context',''))] if args.get('goal') else [])
  if not tasks or len(tasks)>s['limit']:raise ValueError('Передайте от 1 до '+str(s['limit'])+' задач; остальные поручите после результата.')
  prepared=[]
  for task in tasks:
   match=re.match(r'^\[specialist:([a-z0-9-]+)\]\s*(.+)',task.get('goal',''),re.S)
   if not match:raise ValueError('Укажите роль в goal: [specialist:designer] задача. Список: team_specialist action=catalog.')
   prepared.append({**task,**store.prepare(match[1],match[2],task.get('context') or '')})
  clean={k:v for k,v in args.items() if k not in {'goal','context'}};clean['tasks']=prepared
  return next_call(clean)
 except (ValueError,TypeError,AttributeError) as e:return json.dumps({'error':str(e)},ensure_ascii=False)

class TeamAgents:
 def __init__(self,root,portable,bridge):
  self.root=pathlib.Path(root);self.portable=portable;self.bridge=bridge;self.store=TeamStore(root)
  from team_chats import TeamChats
  self.chats=TeamChats(root)
  source=pathlib.Path(__file__).resolve().parent/'agent_plugins/freedom-team';target=portable.HOME/'plugins/freedom-team';target.mkdir(parents=True,exist_ok=True)
  for name in ('__init__.py','plugin.yaml'):shutil.copy2(source/name,target/name)
  portable.write(target/'runtime.json',{'app_relative':os.path.relpath(root,target)})
  self.ensure_plugin()
  self.sync_limit(self.store.read()['limit'])
 def ensure_plugin(self):
  """One-time opt-in for this requested feature, preserving all other plugin choices."""
  marker=self.root/'data/team-plugin-installed.json'
  if marker.exists():return
  from hermes_cli import config as native
  path=self.portable.HOME/'config.yaml'
  with native._CONFIG_LOCK:
   cfg=native.read_user_config_raw(path);plugins=cfg.setdefault('plugins',{})
   backup=self.root/'archive/team-personal-chats-20261113/native-config-before.yaml'
   if path.exists() and not backup.exists():backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
   plugins['enabled']=list(dict.fromkeys([*(plugins.get('enabled') or []),'freedom-team']))
   if 'disabled' in plugins:plugins['disabled']=[v for v in plugins['disabled'] if v!='freedom-team']
   native.atomic_config_write(path,cfg)
  self.portable.write(marker,{'plugin':'freedom-team','installed':True})
 def sync_limit(self,value):
  from hermes_cli import config as native
  path=self.portable.HOME/'config.yaml'
  with native._CONFIG_LOCK:
   cfg=native.read_user_config_raw(path)
   if (cfg.get('delegation') or {}).get('max_concurrent_children')==value:return
   backup=self.root/'archive/team-agents-20261113/native-config-before.yaml'
   if path.exists() and not backup.exists():backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,backup)
   cfg.setdefault('delegation',{})['max_concurrent_children']=value
   native.atomic_config_write(path,cfg)
 def register(self,app):
  from aiohttp import web
  async def get(request):return web.json_response(self.store.read())
  async def update(request):
   data=await request.json();result=self.store.update(data)
   if 'limit' in data:self.sync_limit(result['limit'])
   return web.json_response(result)
  async def live(request):
   sid=request.match_info['sid'];await self.bridge.resume(sid)
   return web.json_response(await self.bridge.rpc('subagent.list',session_id=sid))
  async def control(request):
   data=await request.json();sid=request.match_info['sid'];await self.bridge.resume(sid)
   if data.get('action') not in {'stop','steer'} or not isinstance(data.get('subagent_id'),str):raise ValueError('Выберите помощника и действие.')
   args=dict(session_id=sid,subagent_id=data['subagent_id'])
   if data['action']=='steer':
    if not isinstance(data.get('text'),str) or not data['text'].strip() or len(data['text'])>8000:raise ValueError('Напишите поправку.')
    args['text']=data['text']
   return web.json_response(await self.bridge.rpc('subagent.interrupt' if data['action']=='stop' else 'subagent.steer',**args))
  app.router.add_get('/api/team-agents',get);app.router.add_post('/api/team-agents',update)
  app.router.add_get('/api/sessions/{sid}/team-agents',live);app.router.add_post('/api/sessions/{sid}/team-agents',control)
