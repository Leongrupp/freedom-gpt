"""Read GGUF metadata only, without loading tensors or executing model code."""
import struct
def model_metadata(path):
 with open(path,'rb') as stream:
  def number(fmt):
   size=struct.calcsize(fmt);raw=stream.read(size)
   if len(raw)!=size:raise ValueError('Неполный заголовок GGUF.')
   return struct.unpack('<'+fmt,raw)[0]
  def string():
   size=number('Q')
   if size>8*1024**2:raise ValueError('Слишком длинное поле GGUF.')
   raw=stream.read(size)
   if len(raw)!=size:raise ValueError('Неполные метаданные GGUF.')
   return raw.decode('utf8',errors='replace')
  formats={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
  def value(kind,keep=True):
   if kind in formats:return number(formats[kind])
   if kind==8:return string()
   if kind==9:
    sub,count=number('I'),number('Q')
    if sub in formats:stream.seek(struct.calcsize(formats[sub])*count,1)
    elif sub==8:
     for _ in range(count):stream.seek(number('Q'),1)
    else:raise ValueError('Неизвестный массив GGUF.')
    return None
   raise ValueError('Неизвестный тип метаданных GGUF.')
  if stream.read(4)!=b'GGUF' or number('I') not in (2,3):raise ValueError('Нужен GGUF версии 2 или 3.')
  number('Q');count=number('Q')
  if count>100000:raise ValueError('Слишком много полей GGUF.')
  metadata={}
  for _ in range(count):
   key=string();kind=number('I');item=value(kind)
   if key in {'general.architecture','general.file_type','tokenizer.chat_template'} or key.endswith(('.context_length','.nextn_predict_layers','.block_count')):metadata[key]=item
  return metadata

def model_context(path):
 metadata=model_metadata(path)
 context=max((value for key,value in metadata.items() if key.endswith('.context_length') and isinstance(value,int)),default=0)
 if context<64000:raise ValueError('Для Hermes нужна модель с исходным контекстом от 64К. В GGUF найдено: '+str(context or 'неизвестно')+'. Выберите совместимую модель из каталога.')
 return context
