"""Versioned local game progression. Stable badge ids survive future catalog changes."""
VERSION=1

def track(metric,name,en,counter,counter_en,thresholds,titles,titles_en,*,automatic=False,freedom=0,xp=0,description='',description_en=''):
    return dict(metric=metric,name=name,name_en=en,counter=counter,counter_en=counter_en,thresholds=thresholds,
                titles=titles.split('|'),titles_en=titles_en.split('|'),automatic=automatic,freedom=freedom,xp=xp,
                description=description,description_en=description_en)

TRACKS=[
 track('sites','Веб-архитектор','Web architect','Готовых сайтов','Completed websites',[1,3,10,25,50,100,250],
       'Первый запуск сайта|Веб-мастер|Квартал сайтов|Архитектор веба|Создатель миров|Город в интернете|Веб-легенда',
       'First website launch|Web maker|Website district|Web architect|World builder|An online city|Web legend',freedom=120,xp=200),
 track('apps','Приложения','App maker','Готовых приложений','Completed applications',[1,3,10,25,50,100],
       'Первое приложение|Сборщик решений|Разработчик продуктов|Инженер систем|Архитектор приложений|Мастер продуктов',
       'First application|Solution builder|Product developer|Systems engineer|App architect|Product master',freedom=150,xp=240),
 track('code_tasks','Вайбкодинг','Vibe coding','Готовых задач с кодом','Completed coding tasks',[1,5,20,50,100,500,1000],
       'Первый коммит идей|Вайбкодер|Укротитель функций|Кодовый поток|Сеньор своего мира|Архитектор логики|Легенда кода',
       'First idea commit|Vibe coder|Function tamer|Code flow|Senior of your own world|Logic architect|Code legend',freedom=35,xp=60),
 track('images','Художник','Visual artist','Создано изображений','Generated images',[1,5,10,25,50,100,500,1000],
       'Первый кадр|Ловец идей|Художник пикселей|Мастер света|Фабрика образов|Визуальный архитектор|Галерея Freedom|Легенда холста',
       'First frame|Idea catcher|Pixel artist|Light master|Image factory|Visual architect|Freedom gallery|Canvas legend',automatic=True,freedom=15,xp=30),
 track('videos','Режиссёр','Film director','Создано видео','Generated videos',[1,3,10,25,50,100],
       'Мотор!|История в движении|Монтажная магия|Режиссёр миров|Киностудия на ПК|Легенда кадра',
       'Action!|Story in motion|Editing magic|Director of worlds|A studio on your PC|Frame legend',automatic=True,freedom=40,xp=80),
 track('games','Игры и моды','Games and mods','Игровых результатов','Game projects and reports',[1,3,10,25,50,100],
       'Игроман-создатель|Первые механики|Гейм-мастер|Создатель вселенных|Студия в одиночку|Легенда геймдева',
       'Gamer and creator|First mechanics|Game master|Universe builder|One-person studio|Game development legend',freedom=90,xp=160,
       description='Игры, разрешённые моды, игровые прототипы и отчёты о тестировании.',description_en='Games, permitted mods, playable prototypes and playtest reports.'),
 track('security','Киберзащита','Cybersecurity','Аудитов и отчётов','Security audits and reports',[1,3,10,25,50,100,250],
       'Белая шляпа|Детектив ошибок|Пентестер|Охотник за уязвимостями|Архитектор защиты|Хранитель систем|Легенда киберзащиты',
       'White hat|Bug detective|Pentester|Vulnerability hunter|Defense architect|System guardian|Cybersecurity legend',freedom=100,xp=180,
       description='Разрешённые аудиты, защитный анализ и отчёты об исправлении уязвимостей.',description_en='Authorized audits, defensive analysis and vulnerability remediation reports.'),
 track('seo','SEO-мастер','SEO specialist','SEO-результатов','Completed SEO results',[1,5,15,30,75,150],
       'Первый шаг в поиске|SEO-разведчик|Мастер семантики|Архитектор видимости|Стратег поиска|Легенда органики',
       'First search step|SEO scout|Semantic master|Visibility architect|Search strategist|Organic legend',freedom=65,xp=110),
 track('analysis','Аналитик','Analyst','Аналитических результатов','Completed analysis results',[1,5,15,30,75,150],
       'Первая находка|Детектив данных|Аналитический взгляд|Мастер закономерностей|Архитектор решений|Легенда анализа',
       'First discovery|Data detective|Analytical eye|Pattern master|Decision architect|Analysis legend',freedom=55,xp=100),
 track('automation','Автоматизация','Automation','Готовых автоматизаций','Completed automations',[1,3,10,25,50,100],
       'Первый автопилот|Укротитель рутины|Инженер потоков|Дирижёр процессов|Фабрика без рутины|Легенда автоматизации',
       'First autopilot|Routine tamer|Flow engineer|Process conductor|An effortless factory|Automation legend',freedom=70,xp=120),
 track('three_d','3D-мастерская','3D workshop','Готовых 3D-результатов','Completed 3D results',[1,3,10,25,50,100],
       'Первый объём|Скульптор идей|Мастер геометрии|Архитектор форм|Создатель измерений|Легенда 3D',
       'First volume|Idea sculptor|Geometry master|Form architect|Dimension builder|3D legend',freedom=80,xp=140),
 track('writing','Тексты и знания','Writing and knowledge','Готовых материалов','Completed materials',[1,5,20,50,100,250],
       'Первый материал|Собиратель мыслей|Редактор идей|Автор систем|Библиотека на ПК|Хранитель знаний',
       'First material|Thought collector|Idea editor|Systems author|A library on your PC|Knowledge keeper',freedom=30,xp=55),
 track('learning','Навыки агента','Agent skills','Подтверждено навыков','Confirmed skills',[1,3,10,25,50,100],
       'Первый навык|Наставник агента|Коллекционер приёмов|Мастер обучения|Библиотека мастерства|Легенда навыков',
       'First skill|Agent mentor|Technique collector|Learning master|Mastery library|Skill legend',freedom=45,xp=80,
       description='Сохранённые и проверенные рабочие навыки. Это прогресс использования, а не обучение весов модели.',description_en='Saved, verified working skills. This tracks usage, not model-weight training.'),
 track('turns','Путь с агентом','Agent journey','Завершено ответов','Completed agent turns',[1,10,50,100,500,1000,5000],
       'Первый контакт|На одной волне|Рабочий ритм|Сотня ответов|Постоянный напарник|Тысяча шагов|Неразлучная команда',
       'First contact|On the same wavelength|Working rhythm|A hundred answers|Trusted companion|A thousand steps|Inseparable team',automatic=True,freedom=2,xp=5),
 track('tokens','Вселенная токенов','Token universe','Обработано токенов моделей','Processed model tokens',[1000,10000,100000,1000000,10000000,100000000,1000000000],
       'Первая тысяча|Разогрев контекста|Сто тысяч идей|Миллион токенов|Десять миллионов|Токеновая галактика|Миллиардная вселенная',
       'First thousand|Context warm-up|A hundred thousand ideas|One million tokens|Ten million|Token galaxy|Billion-token universe',automatic=True,
       description='Входные и выходные токены из учёта моделей. Это отдельный счётчик от игровых Freedom.',description_en='Input and output tokens from model usage. This is separate from game Freedom.'),
 track('generated_tokens','Поток ответов','Answer flow','Выходных токенов моделей','Model output tokens',[1000,10000,100000,1000000,10000000,100000000],
       'Первая искра ответа|Слова в потоке|Сто тысяч на выходе|Миллион на выходе|Река идей|Океан ответов',
       'First answer spark|Words in flow|A hundred thousand output tokens|One million output tokens|River of ideas|Ocean of answers',automatic=True),
 track('models','Исследователь моделей','Model explorer','Моделей в истории запросов','Model identifiers used',[1,2,3,5,10,20],
       'Своя нейросеть|Новый взгляд|Три характера|Исследователь моделей|Мастер выбора|Созвездие моделей',
       'Your own AI|A new perspective|Three personalities|Model explorer|Choice master|Model constellation',automatic=True,freedom=10,xp=20),
 track('branches','Ветки идей','Idea branches','Создано веток','Created chat branches',[1,3,10,25,50,100],
       'Первая развилка|Параллельные идеи|Дерево решений|Архитектор вариантов|Сад проектов|Лес возможностей',
       'First fork|Parallel ideas|Decision tree|Variant architect|Project garden|Forest of possibilities',automatic=True,freedom=5,xp=15),
 track('days','Постоянство','Consistency','Активных дней','Active days',[1,3,7,14,30,100,365],
       'День создателя|Три дня в деле|Неделя идей|Две недели в потоке|Месяц созидания|Сотня активных дней|Год вместе',
       'Creator day|Three days in action|A week of ideas|Two weeks in flow|A month of creation|A hundred active days|A year together',automatic=True,freedom=5,xp=10),
 track('streak','Серия создателя','Creator streak','Дней подряд — лучший результат','Longest daily streak',[3,7,14,30,100],
       'Вошёл в ритм|Неделя без пауз|Стабильный поток|Месяц на волне|Железная привычка',
       'Finding your rhythm|A week without pauses|Steady flow|A month on a wave|An iron habit',automatic=True),
]
BY_METRIC={row['metric']:row for row in TRACKS}
MANUAL={key:row for key,row in BY_METRIC.items() if not row['automatic']}
BADGES=[]
TONES=['bronze','silver','gold','violet','diamond','legend','mythic','mythic']
for row in TRACKS:
    assert len(row['thresholds'])==len(row['titles'])==len(row['titles_en'])
    for index,threshold in enumerate(row['thresholds']):
        BADGES.append({'id':row['metric']+':'+str(threshold),'metric':row['metric'],'threshold':threshold,
            'name':row['titles'][index],'name_en':row['titles_en'][index],'tone':TONES[index],
            'freedom':20*(index+1)**2,'xp':45*(index+1)**2})

def public_tracks():
    return [{key:value for key,value in row.items() if key not in ('titles','titles_en')} for row in TRACKS]
