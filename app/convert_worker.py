"""Local file conversion worker. Receives a trusted job spec, emits JSON progress/results."""
import contextlib,csv,io,json,math,os,pathlib,re,shutil,subprocess,sys,time,traceback,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
TOOLS=json.loads((ROOT/'runtime/converter/tools.json').read_text(encoding='utf-8'))
IMAGES={'png','jpg','jpeg','webp','avif','heic','heif','bmp','tif','tiff','gif','ico','svg','tga','psd'}
AUDIO={'mp3','wav','flac','m4a','aac','ogg','opus','wma','aiff','aif'}
VIDEO={'mp4','mkv','mov','avi','webm','m4v','mpeg','mpg','wmv','ts','mts'}
DOCS={'doc','docx','odt','rtf','txt','md','html','htm','epub'}
TABLES={'xlsx','xls','ods','csv','tsv'}
SLIDES={'pptx','ppt','odp'}

def progress(message,percent=None):
    if shutil.disk_usage(ROOT).free<700*1024**2:raise ValueError('На диске осталось меньше 700 МБ. Преобразование остановлено, оригинал сохранён.')
    print(json.dumps({'progress':message,'percent':percent},ensure_ascii=True),flush=True)

def command(args,timeout=240):
    result=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,timeout=timeout,creationflags=0x08004000)
    if result.returncode:
        detail=result.stderr.decode('utf-8',errors='replace')[-350:]
        raise ValueError('Не удалось преобразовать файл. '+detail)
    return result.stdout

def check_zip(source):
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            if sum(f.file_size for f in archive.infolist())>512*1024**2:raise ValueError('Документ слишком большой после распаковки (более 512 МБ).')

def text_read(path):
    raw=path.read_bytes()
    for encoding in ('utf-8-sig','utf-16','cp1251'):
        try:return raw.decode(encoding)
        except UnicodeError:pass
    return raw.decode('utf-8',errors='replace')

def office(source,target,out,work):
    check_zip(source)
    profile=work/'office-profile';profile.mkdir(exist_ok=True)
    (profile/'user').mkdir(exist_ok=True)
    (profile/'user/registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>''',encoding='utf-8')
    source_ext=source.suffix.lower()[1:]
    if source_ext=='md':
        import markdown
        html=work/'markdown.html';html.write_text('<meta charset="utf-8">'+markdown.markdown(text_read(source),extensions=['tables','fenced_code']),encoding='utf-8');source=html
    if source_ext in ('html','htm','md'):
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(text_read(source),'html.parser')
        for node in soup(['script','iframe','object','embed','link']):node.decompose()
        for tag in soup.find_all(True):
            for name in list(tag.attrs):
                if name.lower().startswith('on') or name.lower() in ('src','href','srcset','background'):del tag.attrs[name]
        source=work/'safe.html';source.write_text('<meta charset="utf-8">'+str(soup),encoding='utf-8')
    filters={
        'docx':'Office Open XML Text','odt':'writer8','rtf':'Rich Text Format','txt':'Text (encoded):UTF8',
        'xlsx':'Calc MS Excel 2007 XML','ods':'calc8','csv':'Text - txt - csv (StarCalc):44,34,76',
        'tsv':'Text - txt - csv (StarCalc):9,34,76','pptx':'Impress MS PowerPoint 2007 XML','odp':'impress8','epub':'EPUB'}
    if target=='pdf':
        family='calc' if source_ext in TABLES else 'impress' if source_ext in SLIDES else 'writer'
        fmt='pdf:'+family+'_pdf_Export'
    elif target=='html':fmt='html:HTML (StarCalc)' if source_ext in TABLES else 'html:HTML (StarWriter)'
    else:fmt=target+':'+filters[target]
    destination=work/'office-output';destination.mkdir(exist_ok=True)
    command([TOOLS['soffice'],'-env:UserInstallation='+profile.as_uri(),'--headless','--norestore','--nodefault','--nofirststartwizard',
             '--convert-to',fmt,'--outdir',destination,source],300)
    candidates=list(destination.glob('*.'+target))
    if len(candidates)!=1 or not candidates[0].stat().st_size:raise ValueError('Офисный движок не создал файл. Проверьте формат и отсутствие пароля.')
    if target=='html':
        import base64,mimetypes
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(text_read(candidates[0]),'html.parser')
        for tag in soup.find_all('img',src=True):
            asset=(destination/tag['src']).resolve()
            if asset.is_relative_to(destination.resolve()) and asset.is_file():
                mime=mimetypes.guess_type(asset.name)[0] or 'image/png'
                tag['src']='data:'+mime+';base64,'+base64.b64encode(asset.read_bytes()).decode()
        out.write_text(str(soup),encoding='utf-8')
    else:shutil.copy2(candidates[0],out)

def image_open(source):
    from PIL import Image,ImageOps
    import pillow_heif
    pillow_heif.register_heif_opener();Image.MAX_IMAGE_PIXELS=50_000_000
    if source.suffix.lower()=='.svg':
        import xml.etree.ElementTree as ET
        import resvg_py
        tree=ET.fromstring(text_read(source))
        for tag in tree.iter():
            for key,value in list(tag.attrib.items()):
                if key.endswith('href') and not value.startswith(('#','data:image/')):del tag.attrib[key]
                elif ('url(' in value.lower() and not re.fullmatch(r'url\(\s*#[\w-]+\s*\)',value)):del tag.attrib[key]
            if tag.tag.endswith('style') and tag.text and ('url(' in tag.text or '@import' in tag.text):tag.text=''
        data=resvg_py.svg_to_bytes(svg_string=ET.tostring(tree,encoding='unicode'),width=2000)
        opened=Image.open(io.BytesIO(data))
    else:opened=Image.open(source)
    if opened.width*opened.height>50_000_000:raise ValueError('Изображение больше 50 мегапикселей. Сначала уменьшите его.')
    frames=getattr(opened,'n_frames',1)
    result=ImageOps.exif_transpose(opened).copy();opened.close()
    return result,frames

def image_convert(source,target,out,options):
    from PIL import Image
    image,frames=image_open(source);warnings=[]
    if frames>1:warnings.append('Сохранён первый кадр; для анимации используйте раздел «Видео».')
    limit=int(options.get('image_size') or 0)
    if limit:image.thumbnail((limit,limit),Image.Resampling.LANCZOS)
    quality={'small':72,'balanced':88,'high':96}[options.get('quality','balanced')]
    if target in ('jpg','bmp','pdf'):
        white=Image.new('RGB',image.size,'white')
        if 'A' in image.getbands():white.paste(image,mask=image.getchannel('A'))
        else:white.paste(image.convert('RGB'))
        image=white
    fmt={'jpg':'JPEG','tif':'TIFF','pdf':'PDF'}.get(target,target.upper())
    params={'quality':quality} if target in ('jpg','webp','avif') else {'compression':'tiff_deflate'} if target=='tif' else {}
    if target=='ico':
        image.thumbnail((256,256));canvas=Image.new('RGBA',(256,256),(0,0,0,0))
        canvas.paste(image.convert('RGBA'),((256-image.width)//2,(256-image.height)//2));image=canvas
    image.save(out,format=fmt,**params);image.close();return warnings

def ocr_image(source,work,index=0,pdf=False):
    image,_=image_open(source);path=work/f'ocr-{index}.png';image.convert('RGB').save(path);image.close()
    prefix=work/f'ocr-result-{index}'
    command([TOOLS['tesseract'],path,prefix,'--tessdata-dir',TOOLS['tessdata'],'-l','rus+eng','--psm','3',*(['pdf'] if pdf else [])],180)
    return prefix.with_suffix('.pdf') if pdf else prefix.with_suffix('.txt').read_text(encoding='utf-8').strip()

def pdf_convert(source,target,out,work,options):
    import pymupdf
    try:doc=pymupdf.open(source)
    except Exception as exc:raise ValueError('Не удалось прочитать PDF. Проверьте, что это исправный PDF-файл.') from exc
    if doc.needs_pass:raise ValueError('PDF защищён паролем. Сначала откройте и сохраните копию без пароля.')
    if len(doc)>300:raise ValueError('За один раз поддерживается PDF до 300 страниц.')
    warning=[];files=[]
    if target in ('png','jpg'):
        for index,page in enumerate(doc):
            progress(f'Страница {index+1} из {len(doc)}',round((index+1)/len(doc)*95))
            scale=min(2,math.sqrt(20_000_000/(page.rect.width*page.rect.height)))
            path=out.with_name(out.stem+f'-{index+1:03d}.'+target)
            pix=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False);pix.save(path);files.append(path)
    elif target=='pdf':
        if options.get('ocr') and not ''.join(p.get_text() for p in doc).strip():
            combined=pymupdf.open()
            for index,page in enumerate(doc):
                progress(f'Распознаю страницу {index+1} из {len(doc)}',round(index/len(doc)*90))
                path=work/f'page-{index}.png';page.get_pixmap(matrix=pymupdf.Matrix(2,2)).save(path)
                searchable=ocr_image(path,work,index,pdf=True)
                with pymupdf.open(searchable) as part:combined.insert_pdf(part)
            combined.save(out,garbage=4,deflate=True);combined.close()
        else:doc.save(out,garbage=4,deflate=True)
    elif target in ('txt','docx'):
        texts=[page.get_text(sort=True).strip() for page in doc]
        scan=not any(len(text)>15 for text in texts)
        if scan and not options.get('ocr'):raise ValueError('Это скан. Включите «Распознавать текст» для PDF → Word или TXT.')
        if scan:
            for index,page in enumerate(doc):
                progress(f'Распознаю страницу {index+1} из {len(doc)}',round(index/len(doc)*90))
                path=work/f'page-{index}.png';page.get_pixmap(matrix=pymupdf.Matrix(2,2)).save(path)
                texts[index]=ocr_image(path,work,index)
            warning.append('OCR восстановил текст скана; расположение элементов и таблицы могут отличаться.')
        if target=='txt':out.write_text('\n\n'.join(texts),encoding='utf-8')
        elif scan:
            from docx import Document
            result=Document()
            for index,text in enumerate(texts):
                if index:result.add_page_break()
                for para in text.split('\n'):result.add_paragraph(para)
            result.save(out)
        else:
            from pdf2docx import Converter
            doc.close();converter=Converter(str(source))
            try:converter.convert(str(out),multi_processing=False)
            finally:converter.close()
            warning.append('Проверьте перенос таблиц, шрифтов и сложной вёрстки PDF → Word.')
    if not doc.is_closed:doc.close()
    return files or [out],warning

def data_convert(source,target,out):
    import yaml
    from openpyxl import Workbook,load_workbook
    ext=source.suffix.lower()[1:];data=None
    if ext in ('json','yaml','yml'):
        data=json.loads(text_read(source)) if ext=='json' else yaml.safe_load(text_read(source))
    elif ext in ('csv','tsv'):
        text=text_read(source);dialect='excel-tab' if ext=='tsv' else 'excel'
        if ext=='csv':
            try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=',;\t')
            except csv.Error:pass
        data=list(csv.DictReader(io.StringIO(text),dialect=dialect))
    elif ext=='xlsx':
        check_zip(source);wb=load_workbook(source,read_only=True,data_only=True);sheet=wb.active
        if target=='xlsx':wb.close();shutil.copy2(source,out);return []
        if sheet.max_row>200000:wb.close();raise ValueError('Таблица больше 200 000 строк.')
        rows=sheet.iter_rows(values_only=True);headers=[str(x or f'Column {i+1}') for i,x in enumerate(next(rows,[]))]
        data=[dict(zip(headers,row)) for row in rows];wb.close()
    if target=='json':out.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    elif target in ('yaml','yml'):out.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
    else:
        if not isinstance(data,list) or not all(isinstance(row,dict) for row in data):raise ValueError('Для таблицы нужен JSON-массив объектов с одинаковыми полями.')
        headers=list(dict.fromkeys(key for row in data for key in row))
        if len(data)>200000:raise ValueError('Таблица больше 200 000 строк.')
        def cell(value):return json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value) if value is not None else ''
        if target=='xlsx':
            from openpyxl.cell import WriteOnlyCell
            wb=Workbook(write_only=True);sheet=wb.create_sheet('Data')
            header_cells=[]
            for key in headers:
                c=WriteOnlyCell(sheet,value=str(key));c.data_type='s';header_cells.append(c)
            sheet.append(header_cells)
            for row in data:
                # Keep untrusted table values as text, including formula-like strings.
                from openpyxl.cell import WriteOnlyCell
                values=[]
                for key in headers:
                    value=row.get(key)
                    if isinstance(value,(dict,list)):value=cell(value)
                    c=WriteOnlyCell(sheet,value=value)
                    if isinstance(value,str):c.data_type='s'
                    values.append(c)
                sheet.append(values)
            wb.save(out)
        else:
            with out.open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=headers,delimiter='\t' if target=='tsv' else ',');writer.writeheader()
                for row in data:writer.writerow({key:cell(row.get(key)) for key in headers})
    return ['Экспортирован активный лист; формулы экспортируются как последние сохранённые значения.'] if ext=='xlsx' and target!='xlsx' else []

def media(source,target,out,options):
    metadata=json.loads(command([TOOLS['ffprobe'],'-v','error','-show_streams','-show_format','-of','json',source],30))
    streams=metadata.get('streams',[]);duration=float(metadata.get('format',{}).get('duration') or 0)
    video=next((s for s in streams if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)
    audio=next((s for s in streams if s['codec_type']=='audio'),None)
    opts=['-nostdin','-hide_banner','-loglevel','error','-y','-protocol_whitelist','file,pipe','-i',str(source)]
    quality=options.get('quality','balanced');warning=[];fast=False
    if target in ('mp4','mov','mkv') and video and video.get('codec_name')=='h264' and not options.get('video_size') and quality=='balanced' and (not audio or audio.get('codec_name')=='aac'):
        opts+=['-map','0:v:0','-map','0:a:0?','-c','copy'];fast=True
    elif target in VIDEO or target=='gif':
        if not video:raise ValueError('В файле нет видеодорожки.')
        size=int(options.get('video_size') or 0)
        if target=='gif':
            opts+=['-t','15','-an','-vf','fps=12,scale=640:-2:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse'];duration=min(duration,15)
            warning.append('GIF ограничен первыми 15 секундами и шириной 640 пикселей.')
        else:
            opts+=['-map','0:v:0','-map','0:a:0?']
            opts+=['-vf',f'scale=-2:trunc(min({size}\\,ih)/2)*2' if size else 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
            if target=='webm':opts+=['-c:v','libvpx-vp9','-deadline','realtime','-cpu-used','6','-crf','34','-b:v','0','-c:a','libopus']
            elif target=='avi':opts+=['-c:v','mpeg4','-q:v','4','-c:a','libmp3lame']
            else:opts+=['-c:v','libx264','-preset','veryfast','-crf',{'small':'28','balanced':'23','high':'18'}[quality],'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k']
    else:
        if not audio:raise ValueError('В файле нет звуковой дорожки.')
        opts+=['-map','0:a:0','-vn']
        codecs={'mp3':['-c:a','libmp3lame','-q:a','2'],'wav':['-c:a','pcm_s16le'],'flac':['-c:a','flac'],
                'm4a':['-c:a','aac','-b:a','192k'],'ogg':['-c:a','libvorbis','-q:a','5'],'opus':['-c:a','libopus','-b:a','128k'],'aac':['-c:a','aac','-b:a','192k']}
        opts+=codecs[target]
    if target in ('mp4','mov','m4a'):opts+=['-movflags','+faststart']
    budget=shutil.disk_usage(ROOT).free-1024**3
    if budget<100*1024**2:raise ValueError('Для обработки медиа нужно хотя бы 1,1 ГБ свободного места.')
    opts+=['-threads','4','-fs',str(budget),'-progress','pipe:1','-nostats',str(out)]
    progress('Быстро меняю контейнер без перекодирования' if fast else 'Преобразую аудио или видео',1)
    with (out.parent/'ffmpeg.log').open('wb') as log:
        process=subprocess.Popen([TOOLS['ffmpeg'],*opts],cwd=ROOT,stdout=subprocess.PIPE,stderr=log,creationflags=0x08004000,text=True,encoding='utf-8')
        last=-1
        for line in process.stdout:
            key,_,value=line.strip().partition('=')
            if key=='out_time_us' and duration>0:
                percent=min(98,int(int(value)/1_000_000/duration*100))
                if percent>last:last=percent;progress('Преобразую аудио или видео',percent)
        if process.wait():raise ValueError('FFmpeg не смог преобразовать файл. Проверьте дорожки и формат; подробности в журнале задания.')
    if out.stat().st_size>=budget-1024**2:raise ValueError('Полный результат не помещается на диск. Неполный файл не отмечен готовым; выберите сжатый формат.')
    return warning

def convert_one(source,target,out,work,options):
    ext=source.suffix.lower()[1:];warnings=[]
    if ext=='pdf':return pdf_convert(source,target,out,work,options)
    if ext=='gif' and target in VIDEO:warnings+=media(source,target,out,options)
    elif ext in IMAGES:
        if target in ('txt','docx'):
            text=ocr_image(source,work)
            if target=='txt':out.write_text(text,encoding='utf-8')
            else:
                from docx import Document
                document=Document();document.add_paragraph(text);document.save(out)
            warnings.append('Распознан текст изображения; исходная вёрстка не восстанавливается.')
        elif target=='pdf' and options.get('ocr'):shutil.copy2(ocr_image(source,work,pdf=True),out)
        else:warnings+=image_convert(source,target,out,options)
    elif ext in AUDIO|VIDEO or (ext=='gif' and target in VIDEO):warnings+=media(source,target,out,options)
    elif ext in ('json','yaml','yml','csv','tsv','xlsx') and target in ('json','yaml','yml','csv','tsv','xlsx'):warnings+=data_convert(source,target,out)
    elif ext in DOCS|TABLES|SLIDES:office(source,target,out,work)
    elif ext in ('srt','vtt') and target in ('srt','vtt'):command([TOOLS['ffmpeg'],'-nostdin','-v','error','-y','-i',source,out],30)
    else:raise ValueError('Это преобразование не поддерживается.')
    return [out],warnings

def main(spec):
    if not re.fullmatch('[a-f0-9]{32}',spec['id']):raise ValueError('Invalid conversion identifier')
    folder=(ROOT/'output/converter'/spec['id']).resolve()
    if not folder.is_relative_to((ROOT/'output/converter').resolve()):raise ValueError('Invalid conversion destination')
    folder.mkdir(parents=True,exist_ok=True)
    target=spec['target'];options=spec.get('options') or {};sources=[]
    for item in spec['files']:
        source=(ROOT/item['path']).resolve()
        if not source.is_relative_to((ROOT/'uploads/converter').resolve()) or not source.is_file():raise ValueError('Invalid conversion source')
        ext=source.suffix.lower()[1:];limit=50*1024**2 if ext in ('json','yaml','yml','csv','tsv','html','htm','md','txt') else 200*1024**2
        if ext not in AUDIO|VIDEO and source.stat().st_size>limit:raise ValueError('Слишком большой документ. Лимит: 50 МБ для текста и данных, 200 МБ для документов и фото.')
        sources.append((source,item['name']))
    work=folder/'.work';work.mkdir(exist_ok=True);results=[];warnings=[]
    for index,(source,name) in enumerate(sources):
        progress('Обрабатываю '+name,round(index/len(sources)*90))
        stem=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',pathlib.Path(name).stem)[:85].strip(' .') or 'file'
        output=folder/(f'{index+1:02d}_'+stem+'_converted.'+target)
        sub=work/str(index);sub.mkdir(exist_ok=True)
        files,notes=convert_one(source,target,output,sub,options);results+=files;warnings+=notes
    if options.get('merge') and target=='pdf' and len(results)>1:
        import pymupdf
        merged=pymupdf.open()
        for item in results:
            with pymupdf.open(item) as doc:merged.insert_pdf(doc)
        if len(merged)>500:raise ValueError('В объединённом PDF больше 500 страниц.')
        path=folder/'combined.pdf';merged.save(path,garbage=4,deflate=True);merged.close();results=[path]
    if len(results)>1:
        path=folder/'converted-files.zip'
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
            for item in results:archive.write(item,item.name)
        results.insert(0,path)
    for item in results:
        if not item.is_file() or item.stat().st_size==0:raise ValueError('Движок создал пустой файл.')
    return {'ok':True,'files':[{'path':str(p.relative_to(ROOT)),'name':p.name,'bytes':p.stat().st_size} for p in results],
            'warnings':list(dict.fromkeys(warnings))}

if __name__=='__main__':
    try:
        # Suppress third-party stdout without suppressing our progress protocol.
        payload=json.loads(sys.stdin.read());started=time.monotonic();result=main(payload);result['seconds']=round(time.monotonic()-started,3)
    except BaseException as exc:
        traceback.print_exc(file=sys.stderr);result={'ok':False,'error':str(exc)[:450]}
    print(json.dumps(result,ensure_ascii=True),flush=True)
