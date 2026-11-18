import React,{useState} from 'react';
import {windowTypes} from './RoomLayout.js';
export default function WindowEditor({layout,state}){
 const [open,setOpen]=useState(false);
 if(!state)return null;
 const current=state.windows.find(p=>p.id===state.selected);
 return <aside className="vr-window-editor"><button aria-expanded={open} onClick={()=>setOpen(!open)}>▦ Окна и расстановка</button>{open&&<div className="vr-window-tools">
 <label>Выбранное окно<select aria-label="Окно VR" value={state.selected} onChange={e=>layout.select(e.target.value)}>{state.windows.map((p,i)=><option key={p.id} value={p.id}>{i+1}. {p.title}</option>)}</select></label>
 <label className="vr-edit-toggle"><input type="checkbox" checked={state.editing} onChange={e=>layout.setEditing(e.target.checked)}/> Перетаскивать за любую свободную область</label>
 <p>Тяните заголовок мышью. Alt + перетаскивание — поворот. Колесо — расстояние, Shift + колесо — размер.</p>
 <div className="vr-transform-buttons">{[['←','left','Влево'],['↑','up','Выше'],['→','right','Вправо'],['Ближе','near','Ближе'],['↓','down','Ниже'],['Дальше','far','Дальше'],['↶','yaw-left','Повернуть влево'],['Наклон ↑','tilt-up','Наклон вверх'],['↷','yaw-right','Повернуть вправо'],['−','smaller','Уменьшить окно'],['Наклон ↓','tilt-down','Наклон вниз'],['+','bigger','Увеличить окно']].map(([text,action,label])=><button key={action} aria-label={label} onClick={()=>layout.transform(action)}>{text}</button>)}</div>
 <div className="vr-editor-actions"><button onClick={()=>layout.transform('face')}>Лицом ко мне</button><button disabled={current?.kind==='controls'} onClick={()=>layout.remove()}>Закрыть окно</button></div>
 <label>Новый экран<select aria-label="Тип нового экрана" value={state.type} onChange={e=>layout.setType(e.target.value)}>{windowTypes.map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label>
 <button disabled={!state.canAdd} onClick={()=>layout.add()}>Добавить экран</button>
 <p>Дополнительные экраны показывают данные текущего чата. Расстановка сохраняется автоматически.</p>
 <div className="vr-editor-actions"><button onClick={()=>layout.toggleEditor()}>Пульт внутри VR</button><button onClick={()=>layout.reset()}>Сбросить окна</button></div>
 </div>}</aside>
}
