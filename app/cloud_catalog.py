"""Curated free allocations, verified against primary sources on 2026-10-21."""
CHECKED='2026-10-21'
PROVIDERS={
 'openrouter':{'name':'OpenRouter','kind':'chat','mark':'OR','recommended':True,'key_url':'https://openrouter.ai/settings/keys','pricing_url':'https://openrouter.ai/pricing','docs_url':'https://openrouter.ai/docs/guides/routing/model-variants/free',
 'summary':'Разные модели для кода и общения. Список обновляется по каталогу провайдера; допускаются только модели :free с нулевой ценой входа и выхода.',
 'quota':'На бесплатном аккаунте обычно 50 запросов в день. Один шаг агента тоже расходует запрос. Доступность моделей меняется.',
 'privacy':'Контекст и результаты инструментов обрабатываются OpenRouter и выбранным поставщиком модели. Проверьте их правила хранения данных.',
 'steps':['Зарегистрируйтесь в OpenRouter. Пополнять баланс для бесплатных моделей не требуется.','Откройте Keys → Create Key. Можно установить нулевой денежный лимит.','Вставьте ключ ниже, проверьте подключение и выберите бесплатную модель.'],
 'base':'https://openrouter.ai/api/v1','daily_cap':50},
 'gemini':{'name':'Google Gemini','kind':'chat','mark':'G','key_url':'https://aistudio.google.com/api-keys','pricing_url':'https://ai.google.dev/gemini-api/docs/pricing','docs_url':'https://ai.google.dev/gemini-api/docs/openai',
 'summary':'Код, диалог и понимание изображений. Подключаются модели с опубликованным бесплатным уровнем, доступные вашему ключу.',
 'quota':'Лимиты зависят от модели, аккаунта и региона; смотрите AI Studio → Rate limits. Для Free Tier не подключайте биллинг к проекту.',
 'privacy':'На бесплатном уровне Google может использовать отправленные данные для улучшения продуктов. Доступность зависит от региона.',
 'steps':['Войдите в Google AI Studio в поддерживаемом регионе.','Создайте API key для проекта на Free Tier, без подключённого биллинга.','Скопируйте ключ сюда. Будут показаны доступные модели из бесплатного списка.'],
 'base':'https://generativelanguage.googleapis.com/v1beta/openai','daily_cap':100,
 'models':[{'remote_id':'gemini-3.8-flash','name':'Gemini 3.8 Flash','context_length':65536,'vision':True},{'remote_id':'gemini-3.5-flash-lite','name':'Gemini 3.5 Flash-Lite','context_length':65536,'vision':True},{'remote_id':'gemini-3.1-flash-lite','name':'Gemini 3.1 Flash-Lite','context_length':65536,'vision':True}]},
 'groq':{'name':'Groq','kind':'chat','mark':'Q','key_url':'https://console.groq.com/keys','pricing_url':'https://console.groq.com/docs/rate-limits','docs_url':'https://console.groq.com/docs/openai',
 'summary':'Быстрый текстовый API с бесплатным тарифом. Groq — отдельный сервис, это не Grok от xAI.',
 'quota':'Для выбранных моделей Free plan: 30 запросов/мин, до 1 000/день и 8 000 токенов/мин. Большой системный контекст агента может не поместиться в этот лимит: тогда используйте Gemini или OpenRouter.',
 'privacy':'Запросы отправляются в Groq. Используйте Free plan: приложение не может определить тариф аккаунта только по ключу.',
 'steps':['Создайте аккаунт Groq Console, оставьте Free plan.','Откройте API Keys → Create API Key. Не подключайте платный план.','Вставьте ключ. Для крупных проектов удобнее провайдер с большим бесплатным лимитом входа.'],
 'base':'https://api.groq.com/openai/v1','daily_cap':100,
 'models':[{'remote_id':'openai/gpt-oss-120b','name':'GPT OSS 120B · Groq','context_length':8192,'vision':False},{'remote_id':'openai/gpt-oss-20b','name':'GPT OSS 20B · Groq','context_length':8192,'vision':False},{'remote_id':'qwen/qwen3.8-27b','name':'Qwen 3.8 27B · Groq','context_length':8192,'vision':False}]},
 'cloudflare':{'name':'Cloudflare Workers AI','kind':'image','mark':'CF','key_url':'https://dash.cloudflare.com/profile/api-tokens','pricing_url':'https://developers.cloudflare.com/workers-ai/platform/pricing/','docs_url':'https://developers.cloudflare.com/workers-ai/get-started/rest-api/',
 'summary':'Генерация изображений FLUX.1 Schnell через API. Веса не скачиваются на компьютер.',
 'quota':'Workers Free: 10 000 Neurons в день на все модели аккаунта. После исчерпания запросы останавливаются. В приложении дополнительно не более 20 изображений/день.',
 'privacy':'Описание картинки отправляется Cloudflare. Нужен Workers Free; на Workers Paid превышение бесплатного лимита может оплачиваться.',
 'steps':['Создайте аккаунт Cloudflare и оставьте Workers Free.','Workers AI → Use REST API: создайте токен с правом Workers AI Read для своего аккаунта.','Скопируйте Account ID (32 символа) из панели и API token. Введите их ниже.'],
 'daily_cap':20}
}
UNAVAILABLE=[
 {'name':'OpenAI / ChatGPT API','reason':'API оплачивается отдельно от ChatGPT. Постоянный бесплатный API для чата в этот каталог не включён.','url':'https://developers.openai.com/api/docs/pricing'},
 {'name':'DeepSeek напрямую','reason':'Прямой API тарифицируется по токенам. Если появится бесплатный вариант DeepSeek в OpenRouter, он попадёт в список только при нулевой цене.','url':'https://api-docs.deepseek.com/quick_start/pricing'},
 {'name':'Grok / xAI','reason':'Опубликованы платные цены API. Промокредиты не считаются постоянным бесплатным тарифом.','url':'https://docs.x.ai/developers/pricing'},
 {'name':'Видео через API','reason':'Подтверждённый общедоступный бесплатный API генерации видео пока не добавлен. Локальная генерация видео остаётся в своём разделе.','url':'https://ai.google.dev/gemini-api/docs/pricing#veo-3.1'}
]
