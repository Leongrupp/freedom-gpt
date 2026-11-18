"""Recognize managed API-only preferences without treating arbitrary CLI envelopes as steers."""

BLOCKS=[('Freedom: reply language',('Отвечай пользователю по-русски:','Отвечай на языке последнего задания пользователя.')),
        ('Freedom: самостоятельная работа',('Ты Freedom GPT, действующий агент на этом компьютере,','Выполняй поручение сам в пределах выданного доступа;'))]
LEGACY='\n\n[Настройки владельца: выполнение и память]\n'


def managed_suffix(text,envelope):
    if not isinstance(text,str) or not isinstance(envelope,dict) or set(envelope)!={'api_text'}:return None
    api=envelope.get('api_text')
    if not isinstance(api,str) or not api.startswith(text):return None
    suffix=api[len(text):]
    if not suffix or len(suffix)>12000:return None
    if suffix.startswith(LEGACY):return suffix
    remaining=suffix
    for index,(name,prefixes) in enumerate(BLOCKS):
        opening='\n\n['+name+']\n';closing='\n[/'+name+']'
        if not remaining.startswith(opening):
            if index==0:return None
            break
        end=remaining.find(closing,len(opening))
        if end<0 or not remaining[len(opening):end].startswith(prefixes):return None
        remaining=remaining[end+len(closing):]
    return suffix if not remaining else None


def retained_api_text(original,new_text):
    suffix=managed_suffix(original.get('text'),original.get('cli_turn_v1'))
    return new_text+suffix if suffix is not None else None
