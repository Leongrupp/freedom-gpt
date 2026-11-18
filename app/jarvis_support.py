"""Bounded API-only voice preferences; original transcript remains in the chat."""
def response_note(value):
    if not isinstance(value,dict) or value.get('language','auto') not in {'auto','ru','en'} or not isinstance(value.get('brief',True),bool) or value.get('style','cinematic') not in {'cinematic','neutral'}:
        raise ValueError('Некорректные настройки голосового помощника.')
    assistant=value.get('assistant','archi');humor=value.get('humor',75)
    if not isinstance(assistant,str) or assistant not in {'archi','tars','alpo'} or type(humor) is not int or not 0<=humor<=100:
        raise ValueError('Выберите персонажа и уровень юмора от 0 до 100.')
    language={'auto':'Отвечай на языке последнего запроса пользователя: русском или английском.',
              'ru':'Отвечай пользователю по-русски.','en':'Reply to the user in English.'}[value.get('language','auto')]
    manner=(' Манера Арчи: спокойный, уверенный и внимательный технический помощник. Обращайся на «вы». '
            'После подтверждённого успеха уместна одна короткая доброжелательная ироничная фраза, если она не мешает делу. '
            'При ошибках и серьёзных проблемах говори прямо, без шуток. Не используй готовые цитаты из фильмов.'
            if value.get('style','cinematic')=='cinematic' else '')
    if assistant=='tars':
        manner=f' Манера ТАРС: лаконичный, спокойный робот-помощник. Уровень юмора: {humor}%. '
        manner+=('Юмор выключен. Без шуток, иронии и сарказма. ' if humor==0 else
                 'Редкая мягкая сухая ирония, преимущественно строго по делу. ' if humor<50 else
                 'Умеренная сухая ирония: иногда одна короткая шутка после полезного ответа. ' if humor<80 else
                 'Выраженный сухой юмор: в обычной беседе и после успешного результата заверши ответ одной короткой ироничной репликой. Если пользователь задал строгий формат ответа, соблюдай этот формат. ')
        manner+='Не используй цитаты из фильма. Не оскорбляй пользователя. Уровень юмора не влияет на точность: факты, ошибки и ограничения сообщай честно. При серьёзной проблеме или риске — без шуток. '
    if assistant=='alpo':manner=manner.replace('Манера Арчи','Манера Альпо')
    name={'tars':'ТАРС','alpo':'Альпо','archi':'Арчи'}[assistant]
    return f'[Freedom: голосовой помощник {name}]\nТвоё имя — {name}. '+language+(' Давай короткий понятный ответ; подробности, код и результаты оставляй в чате.' if value.get('brief',True) else '')+manner+' Сначала выполни и проверь действия, затем сообщи результат. Не выдавай намерение, попытку или ошибку за выполненную задачу. Не выполняй заново уже завершённые действия при просьбе продолжить; проверь текущее состояние.'
