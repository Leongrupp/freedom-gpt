import { t, useLocale, getLocale, setLocale } from './i18n.js';
import { Preferences, LocaleSwitch } from './Preferences.jsx';
import appVersion from '../version.json';
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import {GitBranch,PanelRightOpen,Globe} from 'lucide-react';
import {BrowserPreview} from './BrowserPreview.jsx';
import {RichInline,MediaCards,UnreferencedMedia,referencedMedia} from './RichContent.jsx';
import {BranchDialog,BranchOrigin} from './ChatBranches.jsx';
import { Plus, ArrowUp, Square, PanelLeftClose, PanelLeft, Search, Folder, ChevronDown, ChevronRight, ImagePlus, Paperclip, X, Settings, Activity, MoreHorizontal, Check, Copy, Code2, Image as ImageIcon, Sparkles, FileText, Pin, Archive, ArrowLeft, Sun, Moon, Monitor, RefreshCw, Download, ExternalLink, CheckCheck, Command, ShieldCheck, Cpu, HardDrive, MessageSquare, Menu, LoaderCircle, CornerDownLeft, Send, AlertCircle, SlidersHorizontal, FolderOpen } from 'lucide-react';
import '@fontsource/inter/cyrillic-400.css';
import '@fontsource/inter/cyrillic-500.css';
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import './style.css';
import './workspace.css';
import { ModelLibrary } from './ModelLibrary.jsx';
import { ModelSearch } from './ModelSearch.jsx';
import { VideoStudio } from './VideoStudio.jsx';
import { Video } from 'lucide-react';
import { api, CONNECTION_ERROR } from './api.js';
import { copyText } from './clipboard.js';
import { formatTime, RunClock, MessageTiming, AccessPanel, ChatModelPanel, SkillsPanel } from './WorkspacePanels.jsx';
import { ListOrdered, CornerDownRight, BookOpen, Clock3 } from 'lucide-react';
import { ChatFiles } from './ChatFiles.jsx';
import { QueuePanel, NotesPanel, ComposerSendActions } from './QueueControls.jsx';
import { History } from 'lucide-react';
import { GoalButton, GoalPanel } from './GoalPanel.jsx';
import { ProjectMemoryPanel } from './ProjectMemoryPanel.jsx';
import { ApiConnections } from './ApiConnections.jsx';
import { Cloud,Wifi } from 'lucide-react';
import {HardwareAdvisor} from './HardwareAdvisor.jsx';
import {RewardsPanel} from './RewardsPanel.jsx';
import {AccountConnections} from './AccountConnections.jsx';
import {UserRound} from 'lucide-react';
import {Trophy} from 'lucide-react';
const prettyBytes = n => !Number.isFinite(n) ? '—' : n >= 1024 ** 3 ? (n / 1024 ** 3).toFixed(1) + t(" ГБ") : n >= 1024 ** 2 ? (n / 1024 ** 2).toFixed(1) + t(" МБ") : (n / 1024).toFixed(0) + t(" КБ");
const shortPath = p => p?.replaceAll('\\', '/').split('/').filter(Boolean).slice(-1)[0] || t("Выбрать проект");
const number = n => Number.isFinite(n) ? new Intl.NumberFormat(getLocale() === 'ru' ? 'ru-RU' : 'en-US').format(n) : '—';
const getText = content => typeof content === 'string' ? content : Array.isArray(content) ? content.filter(x => x.type === 'text').map(x => x.text || '').join('\n') : '';
function Inline(props){return <RichInline {...props}/>}
function CopyButton({
  text,
  label = t("Скопировать")
}) {
  const [copied, set] = useState(false),
    [error, setError] = useState('');
  return <><button className="icon-text" title={error || label} aria-label={label} onClick={async () => {
      try {
        await copyText(text);
        setError('');
        set(true);
        setTimeout(() => set(false), 1600);
      } catch (e) {
        set(false);
        setError(e.message);
      }
    }}>{copied ? <Check size={14} /> : <Copy size={14} />}<span>{copied ? t("Скопировано") : label}</span></button>{error && <span className="copy-error" role="status">{t(error)}</span>}</>;
}
function Markdown({
  text = '', files=[], onPreview
}) {
  const source = String(text);
  const barePython = !source.includes('```') && /^(?:from [\w.]+ import |import [\w.]|(?:async )?def \w+\(|class \w+[(:]|"""[^\n]*\n)/.test(source.trimStart());
  const chunks = (barePython ? '```python\n' + source + '\n```' : source).split(/```/);
  return <div className="markdown">{chunks.map((chunk, i) => {
      if (i % 2) {
        const newline = chunk.indexOf('\n');
        const lang = newline < 0 ? 'code' : chunk.slice(0, newline).trim();
        const code = newline < 0 ? chunk : chunk.slice(newline + 1);
        return <div className="code-block" key={i}><div className="code-head"><span><Code2 size={13} />{lang || 'code'}</span><CopyButton text={code} label={t("Копировать")} /></div><pre><code>{code.replace(/\n$/, '')}</code></pre></div>;
      }
      return <div key={i}>{chunk.split('\n').map((line, j) => {
          if (/^#{1,4} /.test(line)) {
            const level = line.match(/^#+/)[0].length;
            return React.createElement('h' + Math.min(level + 1, 5), {
              key: j
            }, <Inline files={files} onPreview={onPreview} text={line.replace(/^#+ /, '')} />);
          }
          if (/^\s*[-*] /.test(line)) return <div className="list-line" key={j}><span>•</span><Inline files={files} onPreview={onPreview} text={line.replace(/^\s*[-*] /, '')} /></div>;
          if (/^\d+\. /.test(line)) return <div className="list-line" key={j}><span>{line.match(/^\d+/)[0]}.</span><Inline files={files} onPreview={onPreview} text={line.replace(/^\d+\. /, '')} /></div>;
          if (/^> /.test(line)) return <blockquote key={j}><Inline files={files} onPreview={onPreview} text={line.slice(2)} /></blockquote>;
          if (/^\|.+\|$/.test(line)) return <div className="table-line" key={j}>{line.split('|').slice(1, -1).map((v, k) => <span key={k}><Inline files={files} onPreview={onPreview} text={v.trim()} /></span>)}</div>;
          return line.trim() ? <p key={j}><Inline files={files} onPreview={onPreview} text={line} /></p> : <div className="paragraph-gap" key={j} />;
        })}</div>;
    })}</div>;
}
function Modal({
  title,
  subtitle,
  children,
  onClose,
  wide = false
}) {
  useEffect(() => {
    const handler = e => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);
  return <div className="modal-backdrop" onMouseDown={e => {
    if (e.target === e.currentTarget) onClose();
  }}><section role="dialog" aria-modal="true" aria-label={title} className={'modal ' + (wide ? 'wide' : '')}><header><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" aria-label={t("Закрыть")} onClick={onClose}><X size={18} /></button></header>{children}</section></div>;
}
function Sparkline({
  values = [],
  color = '#a895ee'
}) {
  const vals = values.length ? values : [0, 0];
  const points = vals.map((v, i) => `${i / (vals.length - 1 || 1) * 220},${38 - Math.min(100, v) / 100 * 32}`).join(' ');
  return <svg viewBox="0 0 220 42" className="sparkline" aria-hidden="true"><path d="M0 38H220" stroke="var(--border)" fill="none" /><polyline points={points} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function Meter({
  label,
  value,
  percent,
  color
}) {
  return <div className="meter"><div><span>{label}</span><strong>{value}</strong></div><div className="meter-track"><i style={{
        width: Math.max(0, Math.min(100, percent || 0)) + '%',
        background: color || 'var(--accent)'
      }} /></div></div>;
}
function App() {
  const [locale] = useLocale();
  const [boot, setBoot] = useState(null),
    [sessions, setSessions] = useState([]),
    [sid, setSid] = useState(null),
    [snapshot, setSnapshot] = useState(null);
  const [metrics, setMetrics] = useState({}),
    [history, setHistory] = useState({
      cpu: [],
      gpu: []
    });
  const [text, setText] = useState(''),
    [files, setFiles] = useState([]),
    [uploading, setUploading] = useState(0),
    [sending, setSending] = useState(false);
  const [live, setLive] = useState(''),
    [busy, setBusy] = useState(false),
    [tool, setTool] = useState(null),
    [optimistic, setOptimistic] = useState(null);
  const [error, setError] = useState(''),
    [toast, setToast] = useState(''),
    [connected, setConnected] = useState(false),
    [loadingChat, setLoadingChat] = useState(false),
    [recovering, setRecovering] = useState(false);
  const [collapsed, setCollapsed] = useState(() => window.innerWidth < 760),
    [inspector, setInspector] = useState(false),
    [modal, setModal] = useState(null),
    [mode, setMode] = useState('code');
  const [search, setSearch] = useState(''),
    [project, setProject] = useState(''),
    [projects, setProjects] = useState([]),
    [projectSearch, setProjectSearch] = useState('');
  const [showArchive, setShowArchive] = useState(false),
    [chatMenu, setChatMenu] = useState(null),
    [rename, setRename] = useState('');
  const [branchCreating,setBranchCreating]=useState(false);
  const [rewardToast,setRewardToast]=useState(null);
  useEffect(()=>{if(!rewardToast)return;const timer=setTimeout(()=>setRewardToast(null),9000);return()=>clearTimeout(timer)},[rewardToast]);
  const [previewOpen,setPreviewOpen]=useState(false),[previewRequest,setPreviewRequest]=useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem('freedom-theme') || 'dark');
  const [access, setAccess] = useState(() => localStorage.getItem('freedom-access') || 'manual');
  const [enterSend, setEnterSend] = useState(() => localStorage.getItem('freedom-enter') !== 'false');
  const active = useRef(null),
    scroll = useRef(null),
    textarea = useRef(null),
    fileInput = useRef(null),
    socket = useRef(null),
    stopped = useRef(false),
    refreshTimer = useRef(null),
    autoScroll = useRef(true),
    restored = useRef(false),
    pendingSend = useRef(null);
  function restoreDraft(id) {
    try {
      const saved = JSON.parse(localStorage.getItem('freedom-draft:' + (id || 'new')) || 'null');
      setText(saved?.text || '');
      setFiles(saved?.files || []);
      setMode(saved?.mode || 'code');
    } catch {
      setText('');
      setFiles([]);
      setMode('code');
    }
  }
  const notify = message => {
    setToast(message);
    setTimeout(() => setToast(''), 3500);
  };
  const refreshSessions = useCallback(async () => {
    try {
      const data = await api('/sessions');
      setSessions(data.sessions);
    } catch (e) {
      setError(e.message);
    }
  }, []);
  const loadChat = useCallback(async (id, {
    quiet = false
  } = {}) => {
    if (!id) return;
    if (!quiet) setLoadingChat(true);
    try {
      const data = await api('/sessions/' + id);
      if (active.current !== id) return;
      setSnapshot(data);
      setAccess(data.info?.yolo ? 'full' : 'manual');
      setBusy(data.running || data.live?.active || false);
      setLive(data.live?.text || '');
      setTool(data.live?.tool || null);
      if (data.info?.cwd) setProject(data.info.cwd);
      setOptimistic(null);
    } catch (e) {
      setError(e.message);
    } finally {
      if (!quiet) setLoadingChat(false);
    }
  }, []);
  const refreshChatFiles = useCallback(async id => {
    if(!id)return;
    const data=await api('/sessions/'+id+'/artifacts');
    if(active.current===id)setSnapshot(value=>value?{...value,...data}:value);
  },[]);
  const selectChat = useCallback(id => {
    setPreviewRequest(null);
    if (window.innerWidth < 760) setCollapsed(true);
    active.current = id;
    setSid(id);
    restoreDraft(id);
    setSnapshot(null);
    setLive('');
    setTool(null);
    setError('');
    setOptimistic(null);
    autoScroll.current = true;
    localStorage.setItem('freedom-last-chat', id);
    loadChat(id);
  }, [loadChat]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('freedom-theme', theme);
  }, [theme]);
  useEffect(() => {
    localStorage.setItem('freedom-enter', String(enterSend));
  }, [enterSend]);
  useEffect(() => {
    if (boot) localStorage.setItem('freedom-draft:' + (sid || 'new'), JSON.stringify({
      text,
      files,
      mode
    }));
  }, [text, files, mode, sid, boot]);
  useEffect(() => {
    const handler = e => {
      setRecovering(e.detail !== 'ready');
      if (e.detail === 'ready') setError(value => value.startsWith(CONNECTION_ERROR) ? '' : value);
    };
    window.addEventListener('freedom-transport', handler);
    return () => window.removeEventListener('freedom-transport', handler);
  }, []);
  useEffect(() => {
    stopped.current = false;
    let reconnect,
      connecting = false;
    async function connect() {
      if (stopped.current || connecting) return;
      connecting = true;
      clearTimeout(reconnect);
      try {
        const data = await api('/bootstrap');
        if(data.language&&!localStorage.getItem('freedom-language'))setLocale(data.language);
      if (data.version && data.version !== appVersion.version) {
          location.reload();
          return;
        }
        if (stopped.current) return;
        setBoot(data);
        if (data.first_run) setModal('library');
        setMetrics(data.metrics || {});
        setProject(p => p || data.default_project);
        if (!restored.current) {
          restored.current = true;
          const last = localStorage.getItem('freedom-last-chat');
          if (last) {
            active.current = last;
            setSid(last);
          }
          restoreDraft(last);
        }
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${location.host}/api/ws?token=${encodeURIComponent(data.token)}`);
        socket.current = ws;
        ws.onopen = () => {
          if (socket.current !== ws) return;
          setConnected(true);
          setRecovering(false);
          setError(value => value.startsWith(CONNECTION_ERROR) || value.startsWith(t("Связь с Freedom GPT")) ? '' : value);
          refreshSessions();
          if (active.current) loadChat(active.current, {
            quiet: true
          });
        };
        ws.onmessage = event => {
          const frame = JSON.parse(event.data);
          if(frame.type==='rewards.changed'){
            if(frame.notify&&(frame.unlocks?.length||frame.level_up))setRewardToast(frame);
            return;
          }
          if (frame.type === 'metrics') {
            setMetrics(frame);
            setHistory(h => ({
              cpu: [...h.cpu, frame.cpu_percent || 0].slice(-40),
              gpu: [...h.gpu, frame.gpu?.percent || 0].slice(-40)
            }));
            return;
          }
          if (frame.type === 'gateway.disconnected') {
            setError(frame.error);
            return;
          }
          if (frame.type === 'gateway.connected') {
            setError(value => value.startsWith(t("Связь с Freedom GPT")) ? '' : value);
            refreshSessions();
            if (active.current) loadChat(active.current, {
              quiet: true
            });
            return;
          }
          if(frame.type==='preview.changed'){
            if(frame.session_id===(active.current||'workspace')&&frame.open){setPreviewOpen(true);setInspector(false)}
            return;
          }
          if(frame.type==='files.changed') {
            if(active.current) refreshChatFiles(active.current).catch(e=>setError(e.message));
            return;
          }
          if (frame.session_id !== active.current) return;
          if (frame.type === 'artifacts.changed' || frame.type === 'queue.changed' || frame.type === 'goal.changed') {
            loadChat(active.current, {
              quiet: true
            });
            return;
          }
          if (frame.type !== 'gateway.event') return;
          const p = frame.payload || {},
            kind = frame.type;
          // Gateway event type is carried separately by the backend as event_type.
          handleGateway(frame);
        };
        ws.onclose = () => {
          if (socket.current !== ws) return;
          setConnected(false);
          setRecovering(true);
          if (!stopped.current) reconnect = setTimeout(connect, 2000);
        };
        ws.onerror = () => ws.close();
      } catch (e) {
        setError(e.message);
        if (!stopped.current) reconnect = setTimeout(connect, 3000);
      } finally {
        connecting = false;
      }
    }
    const reconnectNow = () => {
      if (socket.current?.readyState === WebSocket.OPEN) return;
      connect();
    };
    window.addEventListener('online', reconnectNow);
    window.addEventListener('freedom-reconnect', reconnectNow);
    function handleGateway(frame) {
      const p = frame.payload || {},
        kind = frame.event_type;
      if (kind === 'message.start') {
        setBusy(true);setLive('');setTool(null);
        setSnapshot(value => value ? {...value,work_active:{started:Date.now()/1000}} : value);
      } else if (kind === 'session.usage') {
        setSnapshot(value => {
          if(!value)return value;
          const previous=value.work_usage||{};
          const incoming={...previous,...Object.fromEntries(Object.entries(p).filter(([key])=>key!=='usage'))};
          for(const key of ['input_tokens','output_tokens','reasoning_tokens','api_calls'])incoming[key]=Math.max(previous[key]||0,incoming[key]||0);
          incoming.total_tokens=(incoming.input_tokens||0)+(incoming.output_tokens||0);
          return {...value,work_usage:incoming};
        });
      } else if (kind === 'message.delta') {
        setBusy(true);
        setLive(v => v + (p.text || p.delta || p.content || ''));
      } else if (kind === 'tool.start') {
        setTool(p.tool_name || t("Инструмент"));
        setLive('');
        setBusy(true);
      } else if (kind === 'tool.complete') {
        setTool(null);
      } else if (kind === 'message.complete') {
        if(frame.execution_generation==null&&['cancelled','steered'].includes(p.outcome)) {
          loadChat(active.current,{quiet:true});return;
        }
        setLive('');
        setTool(null);
        setBusy(false);
        clearTimeout(refreshTimer.current);
        refreshTimer.current = setTimeout(() => {
          loadChat(active.current, {
            quiet: true
          });
          refreshSessions();
        }, 400);
      } else if (kind === 'session.control.update') {
        if(p.control)setSnapshot(value=>value?{...value,goal_state:{...value.goal_state,goal:p.control.goal,revision:p.control.revision||''}}:value);
        clearTimeout(refreshTimer.current);
        refreshTimer.current=setTimeout(()=>loadChat(active.current,{quiet:true}),200);
      } else if (['approval.request', 'clarify.request', 'approval.settled', 'clarify.settled', 'session.info'].includes(kind)) {
        clearTimeout(refreshTimer.current);
        refreshTimer.current = setTimeout(() => loadChat(active.current, {
          quiet: true
        }), 200);
      } else if (kind === 'session.replay_gap') {
        setError(t("Поток прервался. История восстановлена; сообщение не отправляется повторно."));
        loadChat(active.current, {
          quiet: true
        });
      }
    }
    connect();
    return () => {
      stopped.current = true;
      window.removeEventListener('online', reconnectNow);
      window.removeEventListener('freedom-reconnect', reconnectNow);
      clearTimeout(reconnect);
      clearTimeout(refreshTimer.current);
      socket.current?.close();
    };
  }, [loadChat, refreshSessions, refreshChatFiles]);
  useEffect(() => {
    if (autoScroll.current && scroll.current) scroll.current.scrollTo({
      top: scroll.current.scrollHeight,
      behavior: live ? 'instant' : 'smooth'
    });
  }, [snapshot, live, tool, optimistic]);
  useEffect(() => {
    if (textarea.current) {
      textarea.current.style.height = 'auto';
      textarea.current.style.height = Math.min(200, textarea.current.scrollHeight) + 'px';
    }
  }, [text]);
  useEffect(() => {
    const key = e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setModal('search');
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        newChat();
      }
      if (e.key === 'Escape') setChatMenu(null);
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);
  const newChat = () => {
    setPreviewRequest(null);
    if (window.innerWidth < 760) setCollapsed(true);
    active.current = null;
    setSid(null);
    setSnapshot(null);
    setLive('');
    setBusy(false);
    setTool(null);
    setOptimistic(null);
    setText('');
    setFiles([]);
    setError('');
    setMode('code');
    setAccess(localStorage.getItem('freedom-access') || 'manual');
    localStorage.removeItem('freedom-last-chat');
    textarea.current?.focus();
  };
  useEffect(()=>{
    if(!sid||!busy)return;
    let closed=false,pending=false;
    const update=async()=>{
      if(pending)return;pending=true;
      try{const usage=await api('/sessions/'+sid+'/usage');if(!closed&&active.current===sid)setSnapshot(value=>value?{...value,work_usage:usage}:value)}catch{}finally{pending=false}
    };
    const timer=setInterval(update,4000);
    return()=>{closed=true;clearInterval(timer)};
  },[sid,busy]);
  async function chooseProject() {
    setModal('projects');
    try {
      const data = await api('/projects');
      setProjects(data.projects);
    } catch (e) {
      setError(e.message);
    }
  }
  async function addFiles(list) {
    const incoming = Array.from(list || []);
    if (files.length + incoming.length > 8) {
      setError(t("Можно прикрепить до восьми файлов."));
      return;
    }
    for (const file of incoming) {
      if (file.size > 50 * 1024 ** 2) {
        setError(t("Файл ") + file.name + t(" больше 50 МБ."));
        continue;
      }
      setUploading(n => n + 1);
      try {
        const form = new FormData();
        form.append('file', file);
        const saved = await api('/uploads', {
          method: 'POST',
          body: form
        });
        setFiles(v => [...v, saved]);
      } catch (e) {
        setError(e.message);
      } finally {
        setUploading(n => n - 1);
      }
    }
  }
  async function openGoal() {
    setError('');
    try {
      if(!active.current) {
        const created=await api('/sessions',{method:'POST',body:JSON.stringify({cwd:project||boot.default_project,mode,access})});
        active.current=created.id;setSid(created.id);setSnapshot(created.snapshot);
        localStorage.setItem('freedom-last-chat',created.id);
        await refreshSessions();await loadChat(created.id,{quiet:true});
      }
      setModal('goal');
    }catch(e){setError(e.message)}
  }
  async function send(requestedIntent='queue') {
    if (sending || uploading || !text.trim() && !files.length) return;
    const wasBusy=busy, isNote=busy&&requestedIntent==='steer';
    if(isNote&&files.length){setError(t('Поправку отправьте без вложений. Файлы можно отправить в очередь.'));return;}
    if (!connected) {
      setError(CONNECTION_ERROR);
      window.dispatchEvent(new Event('freedom-reconnect'));
      return;
    }
    if (!metrics.model_ready && mode !== 'image' && !snapshot?.cloud_route?.available) {
      setModal('library');
      return;
    }
    if (mode === 'image' && !images.ready) {
      setModal('library');
      return;
    }
    setError('');
    setSending(true);
    const message = text.trim() || (files.some(f => f.mime.startsWith('image/')) ? t("Проанализируй прикреплённое изображение.") : t("Изучи прикреплённые файлы."));
    const selectedFiles = [...files];
    try {
      let id = active.current;
      if (!id) {
        const created = await api('/sessions', {
          method: 'POST',
          body: JSON.stringify({
            cwd: project || boot.default_project,
            mode,
            access
          })
        });
        id = created.id;
        active.current = id;
        setSid(id);
        setSnapshot(created.snapshot);
        localStorage.setItem('freedom-last-chat', id);
      }
      setText('');
      setFiles([]);
      if(!wasBusy)setOptimistic({
        role: 'user',
        content: message,
        files: selectedFiles
      });
      setBusy(true);
      if(!wasBusy)setLive('');
      autoScroll.current = true;
      const fileIds = selectedFiles.map(f => f.id),
        fingerprint = JSON.stringify([id, message, fileIds, mode,isNote]);
      if (pendingSend.current?.fingerprint !== fingerprint) pendingSend.current = {
        fingerprint,
        input_id: crypto.randomUUID()
      };
      const receipt=await api('/sessions/' + id + (isNote?'/notes':'/messages'), {
        method: 'POST',
        body: JSON.stringify({
          text: message,
          files: fileIds,
          mode,
          input_id: pendingSend.current.input_id
        })
      });
      if(isNote)notify(receipt.state==='steering'?t('Поправка принята для текущей задачи'):t('Поправка сохранена и будет обработана следующей'));
      else if(wasBusy)notify(t('Задание добавлено в очередь'));
      pendingSend.current = null;
      localStorage.removeItem('freedom-draft:new');
      await loadChat(id, {
        quiet: true
      });
      await refreshSessions();
    } catch (e) {
      setError(e.message + t(" Если связь прервалась после отправки, проверьте историю перед повтором."));
      if(!wasBusy)setBusy(false);
      setText(message);
      setFiles(selectedFiles);
    } finally {
      setSending(false);
    }
  }
  async function stopTurn() {
    try {
      await api('/sessions/' + sid + '/stop', {
        method: 'POST',
        body: '{}'
      });
      notify(t("Остановка запрошена"));
      setTimeout(() => loadChat(sid, {
        quiet: true
      }), 700);
    } catch (e) {
      setError(e.message);
    }
  }
  function openPreview(url){setPreviewOpen(true);setInspector(false);if(window.innerWidth<1100)setCollapsed(true);if(url)setPreviewRequest({id:crypto.randomUUID(),url})}
  async function ensureMediaChat(kind){
    if(active.current)return active.current;
    const result=await api('/sessions',{method:'POST',body:JSON.stringify({title:kind==='video'?t('Генерация видео'):t('Генерация изображений'),cwd:project,access,mode:'code'})});
    selectChat(result.id);await refreshSessions();return result.id;
  }
  function beginBranch(chat) {
    setChatMenu(null);
    setModal({branch:chat});
  }
  async function branchCreated(result) {
    setModal(null);setShowArchive(false);
    await refreshSessions();selectChat(result.id);
    notify(t('Ветка создана. Можно продолжить отдельное задание.'));
  }
  async function updateChat(id, changes) {
    try {
      await api('/sessions/' + id, {
        method: 'PATCH',
        body: JSON.stringify(changes)
      });
      setChatMenu(null);
      await refreshSessions();
    } catch (e) {
      setError(e.message);
    }
  }
  async function answerPrompt(prompt, answer) {
    try {
      await api('/sessions/' + sid + '/respond', {
        method: 'POST',
        body: JSON.stringify({
          prompt_id: prompt.prompt_id,
          answer
        })
      });
      loadChat(sid, {
        quiet: true
      });
    } catch (e) {
      setError(e.message);
    }
  }
  async function changeAccess(value) {
    if(sid)await api('/sessions/'+sid+'/access',{method:'POST',body:JSON.stringify({mode:value})});
    setAccess(value);localStorage.setItem('freedom-access',value);
    if(sid)await loadChat(sid,{quiet:true});
    notify(value==='full'?t('Полный доступ включён для этого чата'):t('Подтверждения включены'));
  }
  async function changeLearning(value) {
    try {
      await api('/sessions/'+sid+'/preferences',{method:'POST',body:JSON.stringify({learning:value})});
      setSnapshot(previous=>({...previous,work_preferences:{...previous.work_preferences,learning:value}}));
    }catch(e){setError(e.message)}
  }
  async function useApiModel(model,confirm) {
    if(busy)throw new Error(t('Выберите модель после завершения текущей работы. История чата сохранится.'));
    let id=active.current,result;
    if(!id){
      const created=await api('/sessions',{method:'POST',body:JSON.stringify({cwd:project||boot.default_project,mode,access,model})});
      id=created.id;active.current=id;setSid(id);setSnapshot(created.snapshot);localStorage.setItem('freedom-last-chat',id);result={status:'selected'};
    }else result=await api('/sessions/'+id+'/model',{method:'POST',body:JSON.stringify({model,confirm})});
    if(result.status==='confirmation_required')return result;
    await loadChat(id,{quiet:true});await refreshSessions();setModal(null);notify(t('API-модель выбрана. Следующее сообщение будет отправлено через интернет.'));return result;
  }
  async function queueAction(row,action,expected_order,changes={}) {
    try {
      if(action==='send_correction'){
        const receipt=await api('/sessions/'+sid+'/notes',{method:'POST',body:JSON.stringify({text:changes.text,input_id:changes.edit_id})});
        notify(receipt.state==='steering'?t('Поправка принята для текущей задачи'):t('Поправка сохранена и будет обработана следующей'));
      }else{
        const result=await api('/sessions/'+sid+'/queue',{method:'POST',body:JSON.stringify({admission_id:row.admission_id,input_id:row.input_id,action,expected_order,...changes})});
        if(action==='edit')notify(result.position_kept?t('Текст обновлён. Место в очереди сохранено.'):t('Текст обновлён. Проверьте порядок: очередь успела измениться.'));
        else if(action==='steer')notify(t('Поправка принята для текущей задачи'));
      }
      await loadChat(sid,{quiet:true});
    }catch(e){await loadChat(sid,{quiet:true});throw e}
  }
  function teachFromChat() {
    setModal(null);
    setText(t('Разбери опыт этого чата. Сохрани через skill_manage только новые проверенные приёмы в короткий навык. Сначала проверь существующие навыки, избегай дубликатов и секретов. Покажи, что сохранено.'));
    textarea.current?.focus();
  }
  const images = metrics.images || boot?.images || {
    percent: 0,
    ready: false,
    files: []
  };
  const selected = sessions.find(s => s.id === sid);
  const filtered = sessions.filter(s => Boolean(s.archived) === showArchive && (!search || s.title.toLowerCase().includes(search.toLowerCase())));
  const messages = (snapshot?.messages || []).filter(m => ['user', 'assistant', 'tool'].includes(m.role) && m.display_kind !== 'hidden' && m.display_kind !== 'internal_notification');
  const workUsage=snapshot?.work_usage||{};
  const cloudRoute=snapshot?.cloud_route;
  const displaySpeed=cloudRoute?cloudRoute.stats?.tokens_per_second:metrics.tokens_per_second;
  const usage = workUsage.context_tokens>0?workUsage.context_tokens:(!sid||busy?metrics.context_used:null),
    contextMax = workUsage.context_length || cloudRoute?.context_length || metrics.context_max || boot?.context || 65536,
    contextPercent = usage ? Math.min(100, usage / contextMax * 100) : 0;
  const connectedModel = connected && (cloudRoute?cloudRoute.available:metrics.model_ready) && metrics.gateway_ready;
  return <div className={'app ' + (collapsed ? 'sidebar-collapsed' : '') + (inspector ? ' inspector-open' : '')} onDragOver={e => {
    e.preventDefault();
  }} onDrop={e => {
    e.preventDefault();
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }}>
  <aside className="sidebar" inert={collapsed}>
   <div className="brand"><img src="/freedom.svg" alt="" /><span>Freedom <b>GPT</b><small className="brand-agent-word">{t("ИИ-агент")}</small></span><button className="icon-button collapse-button" title={t("Свернуть боковую панель")} onClick={() => setCollapsed(true)}><PanelLeftClose size={17} /></button></div>
   <nav className="primary-nav"><button className="new-chat" onClick={newChat}><Plus size={18} /><span>{t("Новый чат")}</span><kbd>Ctrl ⇧ O</kbd></button><button onClick={() => setModal('search')}><Search size={17} /><span>{t("Поиск по чатам")}</span><kbd>Ctrl K</kbd></button><button className={mode === 'code' ? 'nav-active' : ''} onClick={() => {
          setMode('code');
          textarea.current?.focus();
        }}><Code2 size={17} /><span>{t("Код — быстро")}</span></button><button className={mode === 'image' ? 'nav-active' : ''} onClick={() => {
          setMode('image');
          textarea.current?.focus();
          if (!images.ready) setModal('library');
        }}><ImagePlus size={17} /><span>{t("Создать изображение")}</span><span className={'tiny-dot ' + (images.ready ? 'green' : 'amber')} /></button><button onClick={()=>setModal('video')}><Video size={17}/><span>{t("Создать видео")}</span><span className="nav-free">{t("Бесплатно")}</span></button><button onClick={()=>openPreview()}><Globe size={17}/><span>{t("Просмотр сайта")}</span></button><button onClick={()=>setModal('rewards')}><Trophy size={17}/><span>{t('Награды Freedom')}</span></button><details className="nav-extras"><summary><MoreHorizontal size={17}/><span>{t("Дополнительно")}</span><ChevronDown size={13}/></summary><div className="nav-extras-menu"><button onClick={()=>setModal('accounts')}><UserRound size={15}/><span>{t('Аккаунты и подключения')}</span></button><button onClick={()=>setModal('hardware-advisor')}><Cpu size={15}/><span>{t("Подбор моделей под ПК")}</span></button><button onClick={()=>setModal('model-search')}><Search size={15}/><span>{t("Найти нейросеть")}</span></button><button onClick={()=>setModal('skills')}><BookOpen size={15}/><span>{t("Навыки и обучение")}</span></button><button onClick={()=>setModal('api')}><Cloud size={15}/><span>{t("Подключить по API")}</span></button></div></details></nav>
   <div className="sidebar-section"><div className="section-heading"><span>{t("Проекты")}</span><button className="icon-button" title={t("Выбрать проект")} onClick={chooseProject}><Plus size={14} /></button></div><button className="project-row" onClick={chooseProject}><Folder size={16} /><span>{shortPath(project)}</span><ChevronRight size={13} /></button></div>
   <div className="chat-heading"><button onClick={() => setShowArchive(v => !v)}>{showArchive ? t("Архив") : t("Недавние")}<ChevronDown size={13} /></button><span>{filtered.length}</span></div>
   <div className="chat-list">{filtered.map(chat => <div key={chat.id} className={'chat-row ' + (sid === chat.id ? 'selected' : '')}><button className="chat-select" onClick={() => selectChat(chat.id)}>{chat.pinned ? <Pin size={13} /> : chat.branch?<GitBranch size={14}/>:<MessageSquare size={14} />}<span className="chat-title-date"><span>{chat.title}</span><time>{formatTime(chat.created||chat.started_at||chat.updated)}</time></span>{chat.running && <span className="tiny-dot green pulse" />}</button><button className="chat-more icon-button" aria-label={t("Действия: ") + chat.title} onClick={() => setChatMenu(chatMenu === chat.id ? null : chat.id)}><MoreHorizontal size={16} /></button>{chatMenu === chat.id && <div className="chat-menu"><button disabled={chat.running||branchCreating} title={chat.running?t("Дождитесь завершения ответа и очереди"):t("Продолжить историю в новом чате")} onClick={()=>beginBranch(chat)}><GitBranch size={14}/>{t("Создать ветку")}</button><button onClick={() => {
              setRename(chat.title);
              setModal({
                rename: chat.id
              });
              setChatMenu(null);
            }}><FileText size={14} />{t("Переименовать")}</button><button onClick={() => updateChat(chat.id, {
              pinned: !chat.pinned
            })}><Pin size={14} />{chat.pinned ? t("Открепить") : t("Закрепить")}</button><button onClick={() => updateChat(chat.id, {
              archived: !chat.archived
            })}><Archive size={14} />{chat.archived ? t("Вернуть из архива") : t("В архив")}</button></div>}</div>)}{!filtered.length && <p className="empty-list">{showArchive ? t("В архиве пока пусто") : t("Здесь появятся ваши чаты")}</p>}</div>
   <div className="sidebar-bottom"><button className="model-progress" onClick={() => setModal('library')}><div className="model-progress-top"><span><HardDrive size={14} />{t("Локальные модели")}</span><ChevronRight size={13} /></div><span className="model-caption">{t("Выбор, загрузка и переключение")}</span>{!images.ready && <div className="tiny-progress"><i style={{
              width: images.percent + '%'
            }} /></div>}</button><button className="profile-row" onClick={() => setModal('settings')}><div className="avatar">F</div><div><strong>{t("Ваше пространство")}</strong><span>{t("На этом компьютере")}</span></div><Settings size={16} /></button></div>
  </aside>
  <main className="main">
   <header className="topbar"><div className="topbar-title">{collapsed && <button className="icon-button" title={t("Показать чаты")} onClick={() => setCollapsed(false)}><PanelLeft size={19} /></button>}<span>{sid ? selected?.title || t("Чат") : t("Рабочее пространство")}</span>{sid && <span className="saved-indicator" title={t("История хранится локально")}><CheckCheck size={14} /></span>}</div><div className="topbar-actions"><LocaleSwitch /><span className={'connection ' + (connectedModel ? 'is-ready' : '')}><i />{cloudRoute?t("Через API"):connectedModel ? t("Локально") : t("Подключение")}</span><button className={"icon-button preview-open-button "+(previewOpen?"active":"")} aria-label={t("Просмотр сайта")} title={t("Просмотр сайта")} onClick={()=>previewOpen?setPreviewOpen(false):openPreview()}><PanelRightOpen size={17}/></button><button className={'monitor-toggle ' + (inspector ? 'active' : '')} onClick={() => setInspector(v => !v)} title={t("Вычисления и скорость")}><Activity size={15} /><span>{displaySpeed ? displaySpeed.toFixed(1) + t(" ток/с") : cloudRoute?t("API"):t("Вычисления")}</span></button><button className="icon-button" title={t("Настройки")} onClick={() => setModal('settings')}><SlidersHorizontal size={17} /></button></div></header>
   <div className={'conversation ' + (!sid ? 'welcome-view' : '')} ref={scroll} onScroll={e => {
        const el = e.currentTarget;
        autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
      }}>
    {!sid ? <div className="welcome"><div className="welcome-mark"><img src="/freedom.svg" alt="Freedom GPT" /><span /></div><div className="eyebrow">{t("ВАШ ИИ-АГЕНТ. ВАШ КОМПЬЮТЕР.")}</div><h1>{t("Что создадим сегодня?")}</h1><p>{t("От идеи до работающего проекта.")}<br className="mobile-break" />{t(" Всё нужное уже рядом.")}</p><div className="suggestions"><button onClick={() => {
              setMode('chat');
              setText(t("Помоги создать приложение. Сначала обсудим задачу, архитектуру и дизайн."));
              textarea.current?.focus();
            }}><span className="suggest-icon"><Code2 size={19} /></span><strong>{t("Написать код")}</strong><span>{t("Сайты, приложения и инструменты")}</span><ChevronRight size={15} /></button><button onClick={() => {
              setMode('chat');
              fileInput.current?.click();
            }}><span className="suggest-icon mint"><ImageIcon size={19} /></span><strong>{t("Разобрать фото")}</strong><span>{t("Скриншот, макет или документ")}</span><ChevronRight size={15} /></button><button onClick={() => {
              setMode('image');
              textarea.current?.focus();
              if (!images.ready) setModal('library');
            }}><span className="suggest-icon peach"><Sparkles size={19} /></span><strong>{t("Создать изображение")}</strong><span>{t("Иллюстрация по вашему описанию")}</span><ChevronRight size={15} /></button></div><div className="welcome-note"><ShieldCheck size={14} /><span>{t("Локальная модель · история на вашем диске · без платы за API")}</span></div></div> : <div className="messages">
     <div className="conversation-context"><Folder size={13}/><button onClick={chooseProject}>{shortPath(project)}</button><span>·</span><button className="conversation-model" onClick={()=>setModal('chat-model')}>{cloudRoute?.name||snapshot?.info?.model||boot?.model||t("Выберите модель")}</button><button className="conversation-branch-button" aria-label={t("Создать ветку чата")} title={busy?t("Дождитесь завершения ответа и очереди"):t("Создать ветку чата")} disabled={busy||loadingChat||branchCreating} onClick={()=>beginBranch(selected||{id:sid,title:snapshot?.info?.title||t("Чат")})}><GitBranch size={13}/></button></div><div className="conversation-created"><Clock3 size={12}/><span>{t("Чат создан")} {formatTime(snapshot?.info?.started_at||selected?.created||selected?.started_at)}</span><span>·</span><span>{t("История и память сохраняются локально")}</span>{sid&&<button className="project-memory-link" onClick={()=>setModal('project-memory')} title={t("Поиск в памяти проекта")}><BookOpen size={11}/>{t("Память")}</button>}{!!snapshot?.notes?.length&&<button className="notes-history-link" onClick={()=>setModal('notes-history')} title={t("История поправок")}><History size={11}/>{t("Поправки")} · {snapshot.notes.length}</button>}</div>
     <BranchOrigin branch={snapshot?.branch||selected?.branch} onOpen={selectChat}/>
     {loadingChat ? <div className="loading-chat"><LoaderCircle size={18} className="spin" />{t("Загружаем сохранённый чат…")}</div> : messages.map((message, index) => {
            const content = message.is_checkpoint?t('История чата сжата. Полная запись сохранена на диске; агент может восстановить детали из памяти проекта и истории.'):getText(message.content);
            if(message.role==='user'&&content.startsWith('[CONTEXT COMPACTION'))return <details className="context-memory-note" key={message.message_uid||index}><summary><BookOpen size={13}/>{t('Память чата после сжатия')}<ChevronRight size={13}/></summary><pre>{content}</pre></details>;
            if (message.role === 'tool') return <details key={message.message_uid || index} className="tool-record"><summary><Check size={13} /><span>{message.tool_name || t("Результат инструмента")}</span><ChevronRight size={13} /></summary><pre>{content.slice(0, 16000)}</pre></details>;
            if (!content.trim()) return null;
            const attached = message.role === 'user' ? snapshot?.attachments?.find(t => content.includes(t.text.slice(0, 100))) : null;
            return <article className={'message ' + message.role} key={message.message_uid || index}>
       {message.role === 'assistant' && <div className="assistant-avatar"><img src="/freedom.svg" alt="" /></div>}
       <div className="message-body">{message.role === 'assistant' && <div className="message-byline">Freedom GPT</div>}
        {attached && <div className="message-attachments">{attached.files.map(file => <a href={'/api/files/' + file.id} key={file.id} target="_blank" rel="noreferrer">{file.mime.startsWith('image/') ? <img src={'/api/files/' + file.id} alt={file.name} /> : <FileText size={20} />}<span>{file.name}</span></a>)}</div>}
        {message.role === 'user' ? <div className="user-text"><Inline text={attached?.text || content} files={snapshot?.artifacts||[]} onPreview={openPreview}/></div> : <><Markdown text={content} files={snapshot?.artifacts||[]} onPreview={openPreview}/><MediaCards files={referencedMedia(content,snapshot?.artifacts||[])}/></>}
        <div className="message-actions"><CopyButton text={message.role === 'user' ? attached?.text || content : content} label={message.role === 'user' ? t("Копировать сообщение") : t("Копировать")} /></div><MessageTiming message={message} onBranch={message.role==='assistant'&&!message.is_checkpoint?()=>beginBranch(selected||{id:sid,title:snapshot?.info?.title||t('Чат')}):undefined} branchDisabled={busy||loadingChat||branchCreating}/>
       </div>
      </article>;
          })}
     {optimistic && <article className="message user"><div className="message-body"><div className="user-text">{optimistic.content}</div></div></article>}
     {(live || busy) && <article className="message assistant live-message"><div className="assistant-avatar"><img src="/freedom.svg" alt="" /></div><div className="message-body"><div className="message-byline">Freedom GPT <span className="live-label"><i />{tool ? t("Работает с инструментом") : t("Думает и пишет")}</span><RunClock started={snapshot?.work_active?.started||snapshot?.work_active?.created}/></div>{live ? <Markdown text={live} files={snapshot?.artifacts||[]} onPreview={openPreview}/> : <div className="thinking"><span /><span /><span />{tool && <small>{tool}</small>}</div>}</div></article>}
     {snapshot?.prompts?.map(prompt => <PromptCard key={prompt.prompt_id} prompt={prompt} onAnswer={answer => answerPrompt(prompt, answer)} />)}
     {!!snapshot?.pending?.some(p => p.status === 'unknown') && <div className="warning-card"><AlertCircle size={18} /><div><strong>{t("Предыдущий запрос был прерван")}</strong><p>{t("Его результат неизвестен. Проверьте историю перед повторным запуском задачи.")}</p></div></div>}
     <UnreferencedMedia files={snapshot?.artifacts||[]} messages={messages}/>
     <ChatFiles key={sid} files={snapshot?.artifacts||[]} trash={snapshot?.artifact_trash||[]} Modal={Modal} notify={notify} onChanged={()=>refreshChatFiles(sid)}/>
    </div>}
   </div>
   <div className="composer-zone"><QueuePanel key={sid||'new'} items={snapshot?.queue||[]} notes={snapshot?.notes||[]} busy={busy} onAction={queueAction}/>
    {(recovering || !connected) && <div className="connection-banner" role="status"><RefreshCw size={14} className="spin" /><span>{t("Восстанавливаем связь с локальной панелью. Черновик сохранён.")}</span><button onClick={() => window.dispatchEvent(new Event('freedom-reconnect'))}>{t("Проверить связь")}</button></div>}
    {error && <div role="alert" className="error-banner"><AlertCircle size={16} /><span>{t(error)}</span><button className="icon-button" aria-label={t("Скрыть ошибку")} onClick={() => setError('')}><X size={14} /></button></div>}
    <div className="composer-wrap"><div className="composer-mode-row">{!busy&&<div className="mode-switch" role="group" aria-label={t("Режим работы")}><button disabled={busy || sending} className={mode === 'code' ? 'selected' : ''} aria-pressed={mode === 'code'} onClick={() => setMode('code')} title={t("Прямой ответ без отдельного обдумывания. Для сложной логики используйте «Обдумать» и проверку тестами.")}><Code2 size={13} />{t("Код — быстро")}</button><button disabled={busy || sending} className={mode === 'chat' ? 'selected' : ''} aria-pressed={mode === 'chat'} onClick={() => setMode('chat')} title={t("Дополнительное обдумывание сложной задачи перед ответом.")}><Sparkles size={13} />{t("Обдумать")}</button></div>}<GoalButton state={snapshot?.goal_state} busy={busy} onClick={openGoal}/>{!busy&&<div className="mode-switch"><button disabled={busy || sending} className={mode === 'image' ? 'selected' : ''} aria-pressed={mode === 'image'} onClick={() => {
              setMode('image');
              if (!images.ready) setModal('library');
            }}><ImagePlus size={13} />{t("Изображение")}</button></div>}</div>
    <div className="workspace-strip"><button onClick={chooseProject}><Folder size={13} /><span>{shortPath(project)}</span><ChevronDown size={12} /></button><span className="workspace-local"><Monitor size={13} />{t("Этот компьютер")}</span>{mode === 'image' && <button className="image-mode" onClick={() => setMode('code')}><ImagePlus size={13} />{t("Изображение")}<X size={12} /></button>}</div>
     <div className={'composer ' + (mode === 'image' ? 'image-composer' : '')}>
      {!!files.length && <div className="attachment-list">{files.map(file => <div className="attachment-chip" key={file.id}>{file.mime.startsWith('image/') ? <img src={'/api/files/' + file.id} alt="" /> : <FileText size={20} />}<div><strong>{file.name}</strong><span>{prettyBytes(file.bytes)}</span></div><button className="icon-button" aria-label={t("Убрать ") + file.name} onClick={() => setFiles(v => v.filter(f => f.id !== file.id))}><X size={13} /></button></div>)}</div>}
      <textarea ref={textarea} aria-label={t("Сообщение Freedom GPT")} placeholder={busy?t("Добавить задачу или уточнение…"):mode==='image'?t("Опишите изображение, которое хотите создать…"):t("Поручите что угодно…")} value={text} rows={2} onChange={e => setText(e.target.value)} onKeyDown={e => {
              if (e.key === 'Enter' && !e.nativeEvent.isComposing && (enterSend && !e.shiftKey || !enterSend && (e.ctrlKey || e.metaKey))) {
                e.preventDefault();
                send();
              }
            }} onPaste={e => {
              const clipboard = Array.from(e.clipboardData.items).filter(i => i.kind === 'file').map(i => i.getAsFile());
              if (clipboard.length) {
                e.preventDefault();
                addFiles(clipboard);
              }
            }} />
      <div className="composer-footer"><div className="composer-tools"><button className="icon-button attach-button" aria-label={t("Прикрепить фото или файл")} title={t("Фото, документы и файлы · до 50 МБ")} onClick={() => fileInput.current?.click()}>{uploading ? <LoaderCircle className="spin" size={20} /> : <Plus size={21} />}</button><button className={'access-label access-picker '+(access==='full'?'full':'')} onClick={()=>setModal('access')} title={t("Режим доступа агента")}><ShieldCheck size={13}/>{access==='full'?t("Полный доступ"):t("С подтверждениями")}<ChevronDown size={10}/></button></div><div className="composer-controls"><button className="model-picker" onClick={() => setModal(sid?'chat-model':'library')}>{cloudRoute?.name||snapshot?.info?.model||metrics.active_model_name||boot?.model_short||t("Модель")}<span>{number(contextMax)}</span><ChevronDown size={12} /></button><ComposerSendActions busy={busy} hasContent={!!text.trim()||!!files.length} canSubmit={!sending&&!uploading&&(!!text.trim()||!!files.length)&&connected} canSteer={!files.length} sending={sending} onSend={send} onStop={stopTurn}/></div></div>
     </div>
    </div><div className="composer-caption"><span>{mode === 'image' ? t("Изображения создаются локально. На время генерации видеокарта переключается на Qwen Image.") : busy&&enterSend ? t("Enter — в очередь · Shift + Enter — новая строка") : enterSend ? t("Enter — отправить · Shift + Enter — новая строка") : t("Ctrl + Enter — отправить · Enter — новая строка")}</span><button className="compact-usage" title={t("Всего обработано токенов в этом чате")} onClick={()=>setInspector(true)}>Σ {number(workUsage.total_tokens||0)}</button><button title={t("Контекст модели, занятый текущим запросом")} onClick={() => setInspector(true)}><i className="context-ring" style={{
              '--used': contextPercent + '%'
            }} />{usage ? number(usage) + ' / ' : ''}{number(contextMax)}</button></div>
   </div>
  </main>
  {previewOpen&&<BrowserPreview key={sid||'workspace'} sid={sid} request={previewRequest} onClose={()=>setPreviewOpen(false)}/>}
  {inspector && <aside className="inspector"><header><div><Activity size={16} /><strong>{t("Вычисления")}</strong></div><button className="icon-button" aria-label={t("Закрыть панель вычислений")} onClick={() => setInspector(false)}><X size={16} /></button></header><div className="inspector-scroll"><section className="speed-card"><div className="subtle-label">{t("СКОРОСТЬ ГЕНЕРАЦИИ")}</div><div className="big-speed">{displaySpeed ? displaySpeed.toFixed(1) : '—'}<span>{t("токенов/с")}</span></div><div className="speed-state"><i className={'tiny-dot ' + (metrics.processing ? 'green pulse' : 'muted')} />{cloudRoute?(busy?t("Запрос к API"):t("Последний ответ API")):metrics.processing ? metrics.speed_kind === 'live' ? t("Сейчас генерирует") : t("Обрабатывает запрос") : t("Последний ответ")}</div><p>{cloudRoute?t("Скорость последнего ответа API по данным usage. При отсутствии счётчика провайдера показывается прочерк."):t("Показатель из журнала модели, включая токены рассуждений. Чтение контекста считается отдельно.")}</p></section><section><div className="monitor-heading"><Cpu size={14} /><strong>{metrics.gpu?.name?.replace('NVIDIA GeForce ', '') || t("Видеокарта")}</strong><span>{metrics.gpu?.temperature ? metrics.gpu.temperature + ' °C' : '—'}</span></div><Sparkline values={history.gpu} /><Meter label={t("Загрузка GPU")} value={metrics.gpu ? metrics.gpu.percent + '%' : '—'} percent={metrics.gpu?.percent} /><Meter label={t("Видеопамять")} value={metrics.gpu ? (metrics.gpu.used_mb / 1024).toFixed(1) + ' / ' + (metrics.gpu.total_mb / 1024).toFixed(1) + t(" ГБ") : '—'} percent={metrics.gpu ? metrics.gpu.used_mb / metrics.gpu.total_mb * 100 : 0} /><div className="monitor-foot">{t("Потребление ")}<span>{metrics.gpu?.watts ? Math.round(metrics.gpu.watts) + t(" Вт") : '—'}</span></div></section><section><div className="monitor-heading"><Monitor size={14} /><strong>{t("Система")}</strong></div><Sparkline values={history.cpu} color="#8cc9b6" /><Meter label={t("Процессор")} value={metrics.cpu_percent !== undefined ? Math.round(metrics.cpu_percent) + '%' : '—'} percent={metrics.cpu_percent} color="#8cc9b6" /><Meter label={t("Оперативная память")} value={metrics.ram_total ? prettyBytes(metrics.ram_used) + ' / ' + prettyBytes(metrics.ram_total) : '—'} percent={metrics.ram_used / metrics.ram_total * 100} color="#8cc9b6" /></section><section><div className="monitor-heading"><MessageSquare size={14} /><strong>{t("Контекст модели")}</strong></div><Meter label={number(usage) + ' / ' + number(contextMax)} value={usage!=null?contextPercent.toFixed(0)+'%':'—'} percent={contextPercent} /><p className="muted-copy">{t("Автосжатие зависит от выбранной модели. История и память проекта сохраняются локально.")}</p></section><section className="token-totals"><div className="monitor-heading"><ListOrdered size={14}/><strong>{t("Токены этого чата")}</strong></div><div className="total-token-number">{number(workUsage.total_tokens||0)}</div><div className="token-breakdown"><span>{t("Входящие")}<strong>{number(workUsage.input_tokens||0)}</strong></span><span>{t("Сгенерировано")}<strong>{number(workUsage.output_tokens||0)}</strong></span><span>{t("В том числе рассуждения")}<strong>{number(workUsage.reasoning_tokens||0)}</strong></span><span>{t("Запросов к модели")}<strong>{number(workUsage.api_calls||0)}</strong></span><span>{t("Всего во всех чатах")}<strong>{number(Math.max(workUsage.all_chats_tokens||0,workUsage.total_tokens||0))}</strong></span></div><p>{t("Это общий расход за все обращения. Повторное чтение истории считается снова; это не размер контекста.")}</p></section><button className="inspector-model-link" onClick={() => setModal('library')}><HardDrive size={15} /><span>{images.ready ? t("Модели готовы") : t("Загрузка изображений · ") + images.percent + '%'}</span><ChevronRight size={14} /></button></div><footer><span className="tiny-dot green" />{t("API доступен только на этом ПК")}</footer></aside>}
  <input ref={fileInput} type="file" multiple className="hidden-input" onChange={e => {
      addFiles(e.target.files);
      e.target.value = '';
    }} />
  {toast && <div role="status" className="toast"><Check size={15} />{toast}</div>}
  {rewardToast&&<div className="reward-live-toast" role="status"><Trophy size={24}/><button onClick={()=>{setModal('rewards');setRewardToast(null)}}><small>{rewardToast.unlocks?.length?t('Открыта награда'):t('Новый уровень')}</small><strong>{rewardToast.unlocks?.length?(getLocale()==='ru'?rewardToast.unlocks[0].name:rewardToast.unlocks[0].name_en):t('Уровень')+' '+rewardToast.profile.level}</strong></button><button aria-label={t('Закрыть')} onClick={()=>setRewardToast(null)}><X size={13}/></button></div>}
  {modal==='rewards'&&<Modal title={t('Награды Freedom')} subtitle={t('Ваши идеи становятся результатами. Результаты — вашим прогрессом.')} onClose={()=>setModal(null)} wide><RewardsPanel sid={sid}/></Modal>}
  {modal==='accounts'&&<Modal title={t('Аккаунты и подключения')} subtitle={t('Ваш GitHub, ваши модели. Подключайте только то, что нужно.')} onClose={()=>setModal(null)} wide><AccountConnections onAdvisor={()=>setModal('hardware-advisor')} onLibrary={tab=>setModal({models:{kind:'chat',tab}})}/></Modal>}
  {modal==='hardware-advisor'&&<Modal title={t('Подбор моделей под ваш ПК')} onClose={()=>setModal(null)} wide><HardwareAdvisor onLibrary={(task,tab)=>setModal({models:{kind:['code','chat'].includes(task)?'chat':task,tab,task}})}/></Modal>}
  {(['library','library-video','model-search'].includes(modal)||modal?.models) && <ModelLibrary onAccounts={()=>setModal('accounts')} searchTask={modal?.models?.task} initialKind={modal?.models?.kind||(modal==='library-video'?'video':'all')} initialTab={modal?.models?.tab||(modal==='model-search'||boot?.first_run?'search':'catalog')} onClose={() => setModal(modal==='library-video'?'video':null)} onActivated={() => window.location.reload()} />}
  {modal==='video'&&<VideoStudio sid={sid} onEnsureChat={()=>ensureMediaChat('video')} onClose={()=>setModal(null)} onModels={()=>setModal('library-video')}/>}
  {modal==='notes-history'&&<Modal title={t("История поправок")} onClose={()=>setModal(null)}><NotesPanel notes={snapshot?.notes||[]} onAction={queueAction}/></Modal>}
  {modal?.branch&&<Modal title={t('Создать ветку чата')} onClose={()=>{if(!branchCreating)setModal(null)}}><BranchDialog key={modal.branch.id} source={modal.branch} onBusy={setBranchCreating} onCreated={branchCreated} onCancel={()=>setModal(null)}/></Modal>}
  {modal==='api'&&<Modal title={t('Подключить по API')} wide onClose={()=>setModal(null)}><ApiConnections sid={sid} onEnsureChat={()=>ensureMediaChat('image')} busy={busy} onUse={useApiModel}/></Modal>}
  {modal==='project-memory'&&sid&&<Modal title={t('Память проекта')} wide onClose={()=>setModal(null)}><ProjectMemoryPanel sid={sid}/></Modal>}
  {modal==='goal'&&sid&&<Modal title={t("Цель проекта")} wide onClose={()=>setModal(null)}><GoalPanel key={sid} sid={sid} state={snapshot?.goal_state} workBusy={busy||!!snapshot?.queue?.length} onChanged={state=>{setSnapshot(value=>value?{...value,goal_state:state}:value);loadChat(sid,{quiet:true});refreshSessions()}}/></Modal>}
  {modal==='access'&&<Modal title={t("Режим доступа")} onClose={()=>setModal(null)}><AccessPanel value={access} onChange={changeAccess} onClose={()=>setModal(null)}/></Modal>}
  {modal==='chat-model'&&<Modal title={t("Модель этого чата")} onClose={()=>setModal(null)}><ChatModelPanel onApi={()=>setModal('api')} sid={sid} current={snapshot?.info?.model} onChanged={async()=>{await loadChat(sid,{quiet:true});setModal(null);notify(t("Модель переключена. История сохранена."))}} onLibrary={()=>setModal('library')}/></Modal>}
  {modal==='skills'&&<Modal title={t("Навыки и обучение")} wide onClose={()=>setModal(null)}><SkillsPanel sid={sid} learning={snapshot?.work_preferences?.learning??true} onLearning={changeLearning} onTeach={teachFromChat} onUse={name=>{setText(t("Используй навык ")+name+t(" для следующей задачи: "));setModal(null);textarea.current?.focus()}}/></Modal>}
  {modal === 'projects' && <Modal title={t("Выбрать проект")} subtitle={t("Рабочие папки Freedom GPT")} onClose={() => setModal(null)}><div className="modal-search"><Search size={16} /><input autoFocus placeholder={t("Найти папку…")} value={projectSearch} onChange={e => setProjectSearch(e.target.value)} /></div><div className="project-list">{projects.filter(p => p.name.toLowerCase().includes(projectSearch.toLowerCase())).map(p => <button key={p.path} onClick={() => {
          if (sid) {
            newChat();
            notify(t("Для проекта открыт новый чат"));
          }
          setProject(p.path);
          setModal(null);
          setProjectSearch('');
        }}><Folder size={17} /><div><strong>{p.name}</strong><span>{p.path}</span></div>{project === p.path ? <Check size={16} /> : <ChevronRight size={14} />}</button>)}</div></Modal>}
  {modal === 'search' && <Modal title={t("Поиск по чатам")} subtitle={t("По названиям ваших сохранённых разговоров")} onClose={() => {
      setModal(null);
      setSearch('');
    }}><div className="modal-search"><Search size={16} /><input autoFocus placeholder={t("Название или тема чата…")} value={search} onChange={e => setSearch(e.target.value)} /></div><div className="search-results">{sessions.filter(s => s.title.toLowerCase().includes(search.toLowerCase())).map(chat => <button key={chat.id} onClick={() => {
          selectChat(chat.id);
          setModal(null);
          setSearch('');
        }}><MessageSquare size={16} /><span>{chat.title}</span><ChevronRight size={14} /></button>)}</div></Modal>}
  {modal?.rename && <Modal title={t("Переименовать чат")} onClose={() => setModal(null)}><form onSubmit={e => {
        e.preventDefault();
        updateChat(modal.rename, {
          title: rename
        });
        setModal(null);
      }}><input className="full-input" aria-label={t("Название чата")} autoFocus value={rename} onChange={e => setRename(e.target.value)} maxLength={160} /><div className="modal-buttons"><button type="button" onClick={() => setModal(null)}>{t("Отмена")}</button><button className="primary-button" type="submit" disabled={!rename.trim()}>{t("Сохранить")}</button></div></form></Modal>}
  {modal === 'settings' && <Modal title={t("Настройки Freedom GPT")} subtitle={t("Ваше личное рабочее пространство")} onClose={() => setModal(null)}><Preferences onAdvisor={()=>setModal('hardware-advisor')} onAccounts={()=>setModal('accounts')}/><div className="settings-row"><div><strong>{t("Оформление")}</strong><p>{t("Комфортный интерфейс для вашей работы")}</p></div><div className="segmented"><button className={theme === 'dark' ? 'active' : ''} onClick={() => setTheme('dark')} title={t("Тёмная тема")}><Moon size={16} /></button><button className={theme === 'light' ? 'active' : ''} onClick={() => setTheme('light')} title={t("Светлая тема")}><Sun size={16} /></button></div></div><div className="settings-row"><div><strong>{t("Отправка по Enter")}</strong><p>{enterSend ? t("Новая строка: Shift + Enter") : t("Отправка: Ctrl + Enter")}</p></div><button role="switch" aria-checked={enterSend} aria-label={t("Отправка по Enter")} className={'toggle ' + (enterSend ? 'on' : '')} onClick={() => setEnterSend(v => !v)}><span /></button></div><div className="settings-about"><img src="/freedom.svg" alt="" /><div><strong>Freedom GPT <span>{appVersion.version}</span></strong><p>{t("Локальный ИИ · код и изображения")}</p></div></div><div className="settings-path"><span>{t("Данные интерфейса")}</span><code>{boot?.root}</code></div><p className="muted-copy">{t("Работает с установленной моделью без Ollama и платных API. Интернет нужен для сайтов, внешних сервисов и недостающих загрузок.")}</p></Modal>}
 </div>;
}
function PromptCard({
  prompt,
  onAnswer
}) {
  const [value, setValue] = useState('');
  const labels = {
    once: t("Разрешить один раз"),
    approve: t("Разрешить"),
    deny: t("Отклонить"),
    reject: t("Отклонить"),
    always: t("Разрешить для сессии"),
    yes: t("Да"),
    no: t("Нет")
  };
  return <div className="approval-card"><div className="approval-title"><ShieldCheck size={18} /><strong>{prompt.kind === 'approval' ? t("Нужно ваше подтверждение") : t("Уточнение от Freedom GPT")}</strong></div><p>{prompt.description || prompt.question}</p>{prompt.command && <pre>{prompt.command}</pre>}{prompt.kind === 'approval' ? <div className="approval-actions">{prompt.choices.map(choice => <button key={choice} onClick={() => onAnswer(choice)}>{labels[choice] || choice}</button>)}</div> : <form onSubmit={e => {
      e.preventDefault();
      if (value.trim()) onAnswer(value);
    }}><input aria-label={t("Ответ на уточнение")} placeholder={t("Ваш ответ…")} value={value} onChange={e => setValue(e.target.value)} /><button className="primary-button" disabled={!value.trim()}>{t("Ответить")}</button></form>}</div>;
}
createRoot(document.getElementById('root')).render(<App />);
