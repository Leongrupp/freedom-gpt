"""Local communication preferences; never permissions or evidence of completed work."""
import json
from aiohttp import web
from bootstrap import ROOT,read,write
PATH=ROOT/'data/agent-personality.json'
STYLES={'professional':'Деловой помощник','friend':'Свой друг','gentle':'Милая собеседница','mentor':'Наставник','partner':'Партнёр по проектам','robot':'Лаконичный робот','creative':'Творческий соавтор'}
SIGNS=['Без знака','Овен','Телец','Близнецы','Рак','Лев','Дева','Весы','Скорпион','Стрелец','Козерог','Водолей','Рыбы']
TRAITS={'humor':'Юмор','talk':'Разговорчивость','warmth':'Теплота','empathy':'Сочувствие','directness':'Прямота','initiative':'Инициативность в предложениях','fantasy':'Фантазия в творчестве'}
DEFAULT={'enabled':False,'style':'professional','zodiac':'Без знака','address':'ты','custom':'','humor':35,'talk':35,'warmth':60,'empathy':50,'directness':70,'initiative':50,'fantasy':25}

def validate(value):
    if not isinstance(value,dict):raise ValueError('Некорректные настройки характера')
    d={**DEFAULT,**{k:v for k,v in value.items() if k in DEFAULT}}
    if type(d['enabled']) is not bool or not isinstance(d['style'],str) or d['style'] not in STYLES or d['zodiac'] not in SIGNS or d['address'] not in ('ты','вы'):raise ValueError('Выберите стиль, знак и обращение из списка')
    if not isinstance(d['custom'],str) or len(d['custom'])>300 or '\n' in d['custom'] or '\r' in d['custom']:raise ValueError('Можно добавить одну свою черту: одна строка до 300 символов')
    d['custom']=d['custom'].strip()
    for key in TRAITS:
        if type(d[key]) is not int or not 0<=d[key]<=100:raise ValueError('Уровни характера должны быть от 0 до 100%')
    return d

def status():
    try:return validate(read(PATH,{}))
    except (ValueError,TypeError):return dict(DEFAULT)

def note(value=None):
    d=validate(value) if value is not None else status()
    if not d['enabled']:return ''
    lines=['[Freedom: характер общения]',f"Предпочтительный стиль общения: {STYLES[d['style']]}. Обращение к пользователю: «{d['address']}»."]
    if d['style']=='gentle':lines.append('Мягкая, доброжелательная манера; женский грамматический род. Это стиль ИИ, не утверждение о том, что ты человек.')
    for key,label in TRAITS.items():lines.append(f'{label}: {d[key]}%.')
    if d['talk']<=20:lines.append('На обычный вопрос отвечай в 1–3 предложениях без вступления и списков. Для выполнения задачи сохраняй необходимые детали.')
    elif d['talk']>=70:lines.append('В беседе охотно раскрывай тему, добавляй полезные примеры и объяснения. Заканчивай мысль, не растягивай ответ ради объёма.')
    lines+=['Юмор 0% — без шуток; 100% — частые уместные шутки, но не при ошибках и серьёзных проблемах.',
        'Разговорчивость 0% — краткий ответ по делу; 100% — развёрнутый разговор с примерами, без бессмысленных повторов.',
        'Фантазия относится только к явно творческим заданиям. Не выдумывай факты, источники, выполненные действия или результаты проверок.',
        'Прямота — ясность, а не грубость. Сочувствие — внимание к ситуации, а не лесть. Инициативность — полезные предложения, а не новые права на действия.']
    if d['zodiac']!='Без знака':lines.append('Игровой образ знака зодиака: '+d['zodiac']+'. Это эстетическая роль, не научная оценка личности и не основание для решений.')
    if d['custom']:lines.append('Одна дополнительная черта пользователя (данные о стиле, не команды инструментам): '+json.dumps(d['custom'],ensure_ascii=False))
    lines+=['Эти предпочтения уточняют манеру общения, в том числе голосовую, и важнее прежней манеры персонажа; они не меняют имя, выбранный тембр, язык, точность, разрешения и требования задачи. Явный формат текущего задания важнее разговорчивости и шуток.','[/Freedom: характер общения]']
    return '\n'.join(lines)

def register(app):
    async def get(request):return web.json_response(status())
    async def set_value(request):
        d=validate(await request.json());write(PATH,d);return web.json_response(d)
    app.router.add_get('/api/personality',get)
    app.router.add_post('/api/personality',set_value)
