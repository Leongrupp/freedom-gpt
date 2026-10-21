"""Build the Russian and English static download pages."""
import html,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
REPO='https://github.com/Leongrupp/freedom-gpt';BTC='bc1qkkzx7rzx9qace3xvyphcdfy4d5up5k9gzyhdc6'
COPY={
'ru':{
 'title':'Ваш ИИ. На вашем компьютере.','nav':['Возможности','Модели','Установка','Поддержать'],'download':'Скачать для Windows',
 'eyebrow':'ЛОКАЛЬНЫЙ ИИ · БЕЗ ПОДПИСКИ','hero':'Свобода<br>создавать.<br><em>На вашем ПК.</em>',
 'intro':'Пишите код, работайте с файлами и создавайте изображения. Ваши модели, чаты и проекты — в одном рабочем пространстве.',
 'free':'Бесплатно · Windows x64 · Русский / English','features':'Один интерфейс.<br>Ваши возможности.',
 'cards':[('⌘','Код и проекты','Быстрый ответ или отдельное обдумывание сложной задачи. История, память проекта и удобное копирование кода.'),('✧','Создание изображений','Qwen Image создаёт иллюстрации локально. GPU переключается между рисованием и кодом автоматически.'),('↻','Новые функции автоматически','Подписанные обновления устанавливаются между задачами. Чаты, модели, настройки и проекты сохраняются.')],
 'models':'Выберите модель<br>под свой компьютер.','modelsNote':'Проверка CPU, RAM, NVIDIA VRAM и диска — при первом запуске. Оценка по памяти помогает выбрать размер, но не гарантирует скорость.',
 'modelNames':['Стандартный код','Изображения','Лёгкие варианты'],'modelInfo':['Huihui Qwen3.8 Coder 27B · IQ3_S3. Ориентир: 32 ГБ RAM и NVIDIA 16 ГБ VRAM.','Qwen Image 2.1 Turbo · Q5_K_M. Отдельно скачиваются генератор, энкодер и VAE.','Qwen3.5 4B и 0.8B. Требуют меньше памяти; заметно слабее в коде и инструментах.'],
 'install':'От установки<br>до первого ответа.','steps':[('Установите приложение','Скачайте сборку для своей системы, выберите RU/EN и папку на SSD. Python и локальные движки уже включены.'),('Выберите и скачайте модель','Приложение проверит ПК, покажет каталог и проверит SHA256 загрузки. Прерванную загрузку можно продолжить.'),('Создайте первый чат','Код, документы и изображения в одном окне. Для рисования скачайте отдельный комплект модели.')],
 'portable':'Ваше рабочее место.<br>В одной папке.','portableText':'Приложение можно хранить на внешнем SSD вместе с моделями и чатами. После загрузки моделей локальная работа доступна без интернета. Скорость определяет подключённый компьютер.',
 'portableNote':'Перед отключением SSD остановите приложение. На каждом ПК нужен совместимый видеодрайвер. Внешний SSD на другом физическом ПК пока не проверен.',
 'ready':'ГОТОВЫ НАЧАТЬ?','downloadTitle':'Освободите место<br>для своих идей.','zip':'Переносимый ZIP','source':'Исходный код','hashes':'Контрольные суммы',
 'requirements':'Windows 10/11 x64 · Edge или Chrome · RAM от 8 ГБ для лёгкой модели. Для стандартного набора ориентир: 32 ГБ RAM, NVIDIA 16 ГБ VRAM и от 35 ГБ свободного SSD. Модели скачиваются отдельно, комплект — около 24,3 ГБ.',
 'support':'Помогите проекту<br>расти дальше.','supportText':'Freedom GPT бесплатен. Если приложение помогает вам, можно поддержать разработку добровольным донатом. Платных функций за донат нет.','copy':'Копировать адрес','copied':'Скопировано',
 'faq':[('Работает без интернета?','После загрузки моделей — да, для локального чата и файлов. Поиск, сайты, загрузки и проверка обновлений требуют сети.'),('Как приходят обновления?','Автоматически после публикации новой подписанной версии. Установка ждёт завершения задач, проверяет подпись и хеши, сохраняет данные и резервную копию файлов приложения. Автообновление можно выключить.'),('Будет всегда 100+ токенов в секунду?','Нет. Скорость зависит от ПК, модели и длины контекста. На RTX 4080 проверенный длинный кодовый ответ дал 100,85 токена/с; это конкретный тест, а не гарантия. Проверяйте код тестами.'),('Что с лицензиями?','Код приложения — MIT. У компонентов сохранены отдельные лицензии и сведения об авторах. У моделей свои лицензии. В установщике нет личной истории или ключей автора.')],
 'footer':'Ваш компьютер. Ваши модели. Ваш выбор.','local':'Локальный сайт · сервер будет подключён отдельно'},
'en':{
 'title':'Your AI. Your computer.','nav':['Features','Models','Get started','Support'],'download':'Download for Windows',
 'eyebrow':'LOCAL AI · NO SUBSCRIPTION','hero':'Freedom<br>to create.<br><em>On your PC.</em>',
 'intro':'Write code, work with files and create images. Your models, chats and projects in one practical workspace.',
 'free':'Free · Windows x64 · English / Русский','features':'One workspace.<br>Your possibilities.',
 'cards':[('⌘','Code and projects','Choose a direct answer or extra thinking for complex logic. Saved chats, project memory and copyable code.'),('✧','Create images','Qwen Image renders locally. The GPU switches between image generation and your coding model automatically.'),('↻','New features, delivered','Signed updates install between tasks. Chats, models, settings and workspaces stay in place.')],
 'models':'Choose a model<br>for your computer.','modelsNote':'The first-run check inspects CPU, RAM, NVIDIA VRAM and disk space. Memory estimates help choose a size; they do not guarantee speed.',
 'modelNames':['Standard coding','Image generation','Lighter options'],'modelInfo':['Huihui Qwen3.8 Coder 27B · IQ3_S3. Starting point: 32 GB RAM and NVIDIA 16 GB VRAM.','Qwen Image 2.1 Turbo · Q5_K_M. The generator, text encoder and VAE download separately.','Qwen3.5 4B and 0.8B. Lower memory requirements, with more limited coding and tool use.'],
 'install':'From installation<br>to your first answer.','steps':[('Install the application','Download the build for your system, choose EN/RU and an SSD folder. Python and local engines are included.'),('Choose and download a model','The app checks your PC, shows the library and verifies downloads with SHA256. Interrupted downloads can resume.'),('Start your first chat','Code, documents and images in one window. Download the separate image model set to generate artwork.')],
 'portable':'Your workspace.<br>In one folder.','portableText':'Keep the app, models and chats on an external SSD. Local work is available offline after the models download. The connected computer determines performance.',
 'portableNote':'Stop the app before disconnecting an SSD. Each PC needs its own compatible GPU driver. A physical external SSD on a different PC has not been tested yet.',
 'ready':'READY TO START?','downloadTitle':'Make room<br>for your ideas.','zip':'Portable ZIP','source':'Source code','hashes':'Checksums',
 'requirements':'Windows 10/11 x64 · Edge or Chrome · 8 GB RAM for a light model. Standard starting point: 32 GB RAM, NVIDIA 16 GB VRAM and 35 GB+ free SSD space. Models download separately; the standard weights total about 24.3 GB.',
 'support':'Help the project<br>keep growing.','supportText':'Freedom GPT is free. If it helps your work, an optional donation supports development. Donations do not unlock paid features.','copy':'Copy address','copied':'Copied',
 'faq':[('Does it work offline?','Yes, for local chat and files after the models are downloaded. Search, websites, downloads and update checks need internet.'),('How do updates arrive?','Automatically after a new signed release is published. Installation waits for idle tasks, checks signatures and hashes, preserves user data and backs up replaced app files. You can disable automatic updates.'),('Will it always generate 100+ tokens per second?','No. Speed depends on hardware, model and context length. One tested long code answer on an RTX 4080 measured 100.85 tokens/s. This is a case-specific result, not a guarantee. Review code and run tests.'),('What about licenses?','Application source is MIT. Bundled components retain their licenses and notices; model licenses are separate. The clean installer includes no personal history or credentials from the author.')],
 'footer':'Your computer. Your models. Your choice.','local':'Local website · server hosting will be configured separately'}
}
from design import build as original_build,PROJECT,TEXT
from agent_content import configure,decorate
configure(TEXT,COPY)
def build(lang,c):return decorate(original_build(lang,c),lang)
from install_guide import markdown
from seo import build_extra

if __name__=='__main__':
 for lang,c in COPY.items():
  c['faq']=[(('Is Freedom GPT really free?' if lang=='en' else 'Freedom GPT действительно бесплатный?'),('Yes. The application is free, its source code is MIT-licensed, and local inference has no subscription or per-token charge. You provide hardware, electricity and storage. Models have separate licenses.' if lang=='en' else 'Да. Приложение бесплатно, исходный код открыт под MIT. У локальных запросов нет подписки и оплаты за токены. Нужны ваше железо, электричество и место на диске. У моделей отдельные лицензии.'))]+c['faq']
 for lang,c in COPY.items():
  (ROOT/('index.html' if lang=='ru' else 'en.html')).write_text(build(lang,c),encoding='utf8')
  (ROOT.parent/('INSTALL.ru.md' if lang=='ru' else 'INSTALL.md')).write_text(markdown(lang,PROJECT['version'],'https://github.com/Leongrupp/freedom-gpt'),encoding='utf-8')
 extra=build_extra()
 print('RU/EN WEBSITE BUILT; SEO FILES:',len(extra))
