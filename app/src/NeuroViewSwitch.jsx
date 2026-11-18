import React from 'react';
import {Orbit,MessageSquare,Zap} from 'lucide-react';
import './neurosphere.css';
export class NeuroBoundary extends React.Component{
 state={failed:false};
 static getDerivedStateFromError(){return {failed:true}}
 render(){return this.state.failed?<div className="neuro-loading-shell" role="alert"><div><Orbit size={28}/><p>Не удалось показать карту. Чат и агент продолжают работать.</p><button onClick={()=>this.setState({failed:false})}>Повторить</button><button onClick={this.props.onClose}>Вернуться в чат</button></div></div>:this.props.children}
}
export function NeuroViewSwitch({mode,visible,onChange}){
 return <div className="neuro-view-switch" role="group" aria-label="Вид рабочего пространства"><button aria-label="Показать чат" aria-pressed={!visible} className={!visible?'selected':''} onClick={()=>onChange('chat')}><MessageSquare size={12}/><span>Чат</span></button><button aria-label="Показать Нейросферу" aria-pressed={visible} className={visible?'selected':''} onClick={()=>onChange('map')}><Orbit size={13}/><span>Нейросфера</span></button><button className={mode==='auto'?'auto selected':'auto'} title="Открывать Нейросферу вместе с Арчи" aria-label="Автоматически открывать с Арчи" aria-pressed={mode==='auto'} onClick={()=>onChange(mode==='auto'?'chat':'auto')}><Zap size={11}/></button></div>;
}
