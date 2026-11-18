import MessengerButton from './MessengerButton.jsx';
import {connectionStatus,useVideoActivity} from './connectionStatus.js';
import {localStore,sessionStore} from './browserStorage.js';
import {ContextMenu} from './ContextMenu.jsx';
import {guardStoppedReply} from './progress-guard-state.js';
import {CompletionNotifications} from './CompletionNotifications.jsx';
import {EnhanceCoordinator} from './EnhanceMedia.jsx';
import {publishCompletionFrame} from './completionNotifications.js';
import {TurboControl,useTurbo} from './TurboControl.jsx';
import {RunSettings} from './RunSettings.jsx';
import {RemoteAccessPanel} from './RemoteAccessPanel.jsx';
import {VoiceInput} from './VoiceInput.jsx';
import {Jarvis} from './Jarvis.jsx';
import {useJarvisPreferences} from './jarvisPreferences.js';
import {assistantOptions} from './jarvisPolicy.js';
import {NeuroViewSwitch,NeuroBoundary} from './NeuroViewSwitch.jsx';
import {submitNeuroIdea} from './neuroIdeas.js';
import {FileConverterPanel} from './FileConverterPanel.jsx';
import {ArrowRightLeft} from 'lucide-react';
import {roleName} from './AutoModelsPanel.jsx';
import { t, useLocale, getLocale, getIntlLocale, setLocale } from './i18n.js';
import { Preferences, LocaleSwitch, ProgramUpdate } from './Preferences.jsx';
import appVersion from '../version.json';
import React, { useState, useEffect, useRef, useCallback } from 'react';
const CameraStudioPanel=React.lazy(()=>import('./CameraStudio.jsx').then(module=>({default:module.CameraStudioPanel})));
const CameraPhone=React.lazy(()=>import('./CameraStudio.jsx').then(module=>({default:module.CameraPhone})));
const VRWorkspace=React.lazy(()=>import('./VRWorkspace.jsx'));
const Neurosphere=React.lazy(()=>import('./Neurosphere.jsx'));
const NeuroDevelopment=React.lazy(()=>import('./NeuroDevelopment.jsx'));
import { createRoot } from 'react-dom/client';
import {GitBranch,PanelRightOpen,Globe,Camera} from 'lucide-react';
import {BrowserPreview,PreviewBoundary} from './BrowserPreview.jsx';
import {usePreviewWindow} from './usePreviewWindow.js';
import {RichInline,MediaCards,UnreferencedMedia,referencedMedia} from './RichContent.jsx';
import {serviceMessage,userMessage} from './serviceMessages.js';
import {BranchDialog,BranchOrigin} from './ChatBranches.jsx';
import { Plus, ArrowUp, ArrowDown, Square, PanelLeftClose, PanelLeft, Search, Folder, ChevronDown, ChevronRight, ImagePlus, Paperclip, X, Settings, Activity, MoreHorizontal, Check, Copy, Code2, Image as ImageIcon, Sparkles, FileText, Pin, Archive, ArrowLeft, Sun, Moon, Monitor, RefreshCw, Download, ExternalLink, CheckCheck, Command, ShieldCheck, Cpu, HardDrive, MessageSquare, Menu, LoaderCircle, CornerDownLeft, Send, AlertCircle, SlidersHorizontal, FolderOpen } from 'lucide-react';
import '@fontsource/inter/cyrillic-400.css';
import '@fontsource/inter/cyrillic-500.css';
import '@fontsource/inter/latin-400.css';
import '@fontsource/inter/latin-500.css';
import './style.css';
import MessageMarkdown from './MessageMarkdown.jsx';
import SaveReplySkill from './SaveReplySkill.jsx';
import ResearchButtons from './ResearchButtons.jsx';
import WelcomeBrand from './WelcomeBrand.jsx';
import SidebarBrand from './SidebarBrand.jsx';
import ChatScrollToBottom from './ChatScrollToBottom.jsx';
import {Gamepad2} from 'lucide-react';
const ArcadePanel=React.lazy(()=>import('./ArcadePanel.jsx'));
import './workspace-actions.css';
import {useChatHistory,HistoryPaging,ChatHistoryPanel,BookmarkMessage,HistoryTool,messageKey} from './ChatHistory.jsx';
import './workspace.css';
import './sidebar-tools.css';
import './settings-header.css';
import { ModelLibrary } from './ModelLibrary.jsx';
import {TeamAgentsPanel,TeamCompletion,SpecialistChatHeader} from './TeamAgentsPanel.jsx';
import { ModelSearch } from './ModelSearch.jsx';
import { VideoStudio } from './VideoStudio.jsx';
import { MediaStudio } from './MediaStudio.jsx';
import { Music2 } from 'lucide-react';
import { Video } from 'lucide-react';
import { api, CONNECTION_ERROR } from './api.js';
import { copyText } from './clipboard.js';
import { formatTime, RunClock, MessageTiming, AccessPanel, ChatModelPanel, SkillsPanel } from './WorkspacePanels.jsx';
import { ListOrdered, CornerDownRight, BookOpen, Clock3, Trash2, RotateCcw } from 'lucide-react';
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
import {ActivityMessage,publishActivityFrame} from './LiveActivity.jsx';
import {SpeechCoordinator,ReadAloudButton,SpeechPlayer,readLatestResponse} from './SpeechOutput.jsx';
import {isReadCommand} from './speechText.js';
const prettyBytes = n => !Number.isFinite(n) ? '—' : n >= 1024 ** 3 ? (n / 1024 ** 3).toFixed(1) + t(" ГБ") : n >= 1024 ** 2 ? (n / 1024 ** 2).toFixed(1) + t(" МБ") : (n / 1024).toFixed(0) + t(" КБ");
const shortPath = p => p?.replaceAll('\\', '/').split('/').filter(Boolean).slice(-1)[0] || t("Выбрать проект");
const number = n => Number.isFinite(n) ? new Intl.NumberFormat(getIntlLocale()).format(n) : '—';
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
function Markdown(props) {
  return <MessageMarkdown {...props} renderCopy={code=><CopyButton text={code} label={t("Копировать")} />}/>;
}
function Modal({
  title,
  subtitle,
  children,
  onClose,
  headerActions,
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
  }}><section role="dialog" aria-modal="true" aria-label={title} className={'modal ' + (wide ? 'wide' : '') + (headerActions ? ' has-header-actions' : '')}><header><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{headerActions && <div className="modal-header-controls">{headerActions}</div>}<button className="icon-button" aria-label={t("Закрыть")} onClick={onClose}><X size={18} /></button></header>{children}</section></div>;
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
  const [developmentSeed,setDevelopmentSeed]=useState({});
  const [boot, setBoot] = useState(null),
    [sessions, setSessions] = useState([]),
    [sid, setSid] = useState(null),
    [snapshot, setSnapshot] = useState(null);
  const [metrics, setMetrics] = useState({}),
    [history, setHistory] = useState({
      cpu: [],
      gpu: []
    });
  const turbo=useTurbo(metrics.performance);
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
    [modal, setModal] = useState(()=>new URLSearchParams(location.search).get('vr')==='1'?'vr-workspace':null),
    [mode, setMode] = useState('code');
  const [neuroMode,setNeuroMode]=useState(()=>['auto','chat','map'].includes(localStore.getItem('freedom-neuro-view'))?localStore.getItem('freedom-neuro-view'):'auto');
  const [jarvisEnabled,setJarvisEnabled]=useState(!!window.__freedomJarvisActive);
  const jarvisEnabledRef=useRef(jarvisEnabled);
  const neuroVisible=neuroMode==='map'||neuroMode==='auto'&&jarvisEnabled;
  function changeNeuroView(value){localStore.setItem('freedom-neuro-view',value);setNeuroMode(value)}
  useEffect(()=>{const update=e=>{const enabled=!!(e.detail?.engaged??e.detail?.enabled);if(jarvisEnabledRef.current!==enabled){jarvisEnabledRef.current=enabled;setJarvisEnabled(enabled)}};window.addEventListener('freedom-jarvis-state',update);return()=>window.removeEventListener('freedom-jarvis-state',update)},[]);
  const [thinkingLevel,setThinkingLevel]=useState('low');
  const [webSearch,setWebSearch]=useState(false);
  const [welcomeGeneration,setWelcomeGeneration]=useState(0);
  const assistantPrefs=useJarvisPreferences();
  const [researchBrowser,setResearchBrowser]=useState(()=>localStore.getItem('freedom-research-browser')||'builtin'),[researchEngine,setResearchEngine]=useState(()=>localStore.getItem('freedom-research-engine')||'auto');
  function researchSelection(value){setResearchBrowser(value.browser);setResearchEngine(value.engine);localStore.setItem('freedom-research-browser',value.browser);localStore.setItem('freedom-research-engine',value.engine)}
  useEffect(()=>{if(mode==='image')setWebSearch(false)},[mode]);
  useEffect(()=>{const value=snapshot?.work_preferences?.reasoning;setThinkingLevel(value||'low');setMode(current=>current==='image'?current:value&&value!=='none'?'chat':'code')},[sid,snapshot?.work_preferences?.reasoning]);
  const [search, setSearch] = useState(''),
    [project, setProject] = useState(''),
    [projects, setProjects] = useState([]),
    [projectSearch, setProjectSearch] = useState('');
  const [searchOpen,setSearchOpen]=useState(false),[showTrash,setShowTrash]=useState(false),[deletingChat,setDeletingChat]=useState(false);
  const sidebarSearch=useRef(null);
  useEffect(()=>{if(searchOpen)sidebarSearch.current?.focus()},[searchOpen]);
  const [showArchive, setShowArchive] = useState(false),
    [chatMenu, setChatMenu] = useState(null),
    [rename, setRename] = useState('');
  const [branchCreating,setBranchCreating]=useState(false);
  const [rewardToast,setRewardToast]=useState(null);
  useEffect(()=>{if(!rewardToast)return;const timer=setTimeout(()=>setRewardToast(null),9000);return()=>clearTimeout(timer)},[rewardToast]);
  const previewWindow=usePreviewWindow(sid),previewOpen=previewWindow.view.open,previewRequest=previewWindow.view.request;
  const [theme, setTheme] = useState(() => localStore.getItem('freedom-theme') || 'dark');
  const [access, setAccess] = useState(() => localStore.getItem('freedom-access') || 'manual');
  const enterSend = true;
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
  const chatHistory=useChatHistory(sid,snapshot,scroll,autoScroll);
  function restoreDraft(id) {
    try {
      const saved = JSON.parse(localStore.getItem('freedom-draft:' + (id || 'new')) || 'null');
      setText(saved?.text || '');
      setFiles(saved?.files || []);
      setMode(saved?.mode || 'code');
      setWebSearch(saved?.webSearch===true&&saved?.mode!=='image');
    } catch {
      setText('');
      setFiles([]);
      setMode('code');setWebSearch(false);
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
    localStore.setItem('freedom-last-chat', id);
    loadChat(id);
  }, [loadChat]);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStore.setItem('freedom-theme', theme);
  }, [theme]);
  useEffect(() => {
    if (boot) localStore.setItem('freedom-draft:' + (sid || 'new'), JSON.stringify({
      text,
      files,
      mode,webSearch
    }));
  }, [text, files, mode, webSearch, sid, boot]);
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
        if(data.language&&!localStore.getItem('freedom-language'))setLocale(data.language);
      if ((data.version && data.version !== appVersion.version) ||
          (data.ui_revision && appVersion.ui_revision && data.ui_revision !== appVersion.ui_revision)) {
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
          const last = localStore.getItem('freedom-last-chat');
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
          previewWindow.refresh();
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
          if(frame.type==='auto.changed'&&frame.session_id===active.current){setSnapshot(value=>value?{...value,auto_route:frame.auto_route}:value);}
          if(frame.type==='progress.stopped'){refreshSessions();if(frame.session_id===active.current)loadChat(active.current,{quiet:true});return;}
          if (frame.type === 'gateway.connected') {
            previewWindow.refresh();
            setError(value => value.startsWith(t("Связь с Freedom GPT")) ? '' : value);
            refreshSessions();
            if (active.current) loadChat(active.current, {
              quiet: true
            });
            return;
          }
          if(frame.type==='preview.changed'||frame.type==='preview.finished'){
            previewWindow.receive(frame);
            if(frame.session_id===(active.current||'workspace')&&frame.open)setInspector(false);
            return;
          }
          if(frame.type==='files.changed') {
            if(active.current) refreshChatFiles(active.current).catch(e=>setError(e.message));
            return;
          }
          if(frame.type==='gateway.event'&&frame.event_type==='message.start')previewWindow.receive(frame);
          publishActivityFrame(frame);
          publishCompletionFrame(frame);
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
  }, [snapshot, live, tool, optimistic, chatHistory.messages]);
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
        setCollapsed(false);setSearchOpen(true);sidebarSearch.current?.focus();
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
    setWelcomeGeneration(value=>value+1);
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
    setAccess(localStore.getItem('freedom-access') || 'manual');
    localStore.removeItem('freedom-last-chat');
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
        localStore.setItem('freedom-last-chat',created.id);
        await refreshSessions();await loadChat(created.id,{quiet:true});
      }
      setModal('goal');
    }catch(e){setError(e.message)}
  }
  async function thinkFromNeurosphere(request){
    if(sending||uploading||loadingChat)throw new Error('Дождитесь завершения отправки или загрузки чата.');
    if(!connected)throw new Error('Нет связи с агентом. Дождитесь подключения и повторите.');
    const originSid=active.current;
    const result=await submitNeuroIdea(api,request,{defaultProject:project||boot.default_project,access});
    if(active.current===originSid){
      if(result.sid!==active.current)selectChat(result.sid);
      else await loadChat(result.sid,{quiet:true});
      changeNeuroView('chat');
    }
    refreshSessions().catch(()=>{});notify('Запрос на обдумывание принят. Ответ появится в чате.');
    return result;
  }
  async function send(requestedIntent='queue', voiceInput=null) {
    const voice=voiceInput&&typeof voiceInput==='object'?voiceInput:null;
    const voiceQuestion=voice?.jarvis?.interaction==='question';
    const sendMode=voiceQuestion?'chat':voice?(voice.context.mode==='chat'?'chat':'code'):mode;
    const draftText=voice?voice.text:text, draftFiles=voice?[]:files;
    if (sending || uploading || !draftText.trim() && !draftFiles.length){
      if(voice)throw new Error(t('Дождитесь отправки текущего сообщения. Голосовая запись сохранена.'));
      return;
    }
    if(voice&&(voice.context.sid||null)!==(active.current||null))throw new Error(t('Чат изменился. Вернитесь в исходный чат или вставьте расшифровку вручную.'));
    if(boot?.speech?.enabled&&!draftFiles.length&&isReadCommand(draftText)){
      const spoken=readLatestResponse(snapshot?.messages||[]);
      if(!spoken&&voice)throw new Error(t('В чате пока нет ответа для озвучки.'));
      if(!voice&&spoken)setText('');
      return {state:'spoken'};
    }
    const wasBusy=busy, isNote=(busy||snapshot?.pending?.some(p=>p.status==='unknown'))&&requestedIntent==='steer';
    if(isNote&&files.length){setError(t('Поправку отправьте без вложений. Файлы можно отправить в очередь.'));return;}
    if (!connected) {
      setError(CONNECTION_ERROR);
      window.dispatchEvent(new Event('freedom-reconnect'));
      if(voice)throw new Error(CONNECTION_ERROR);
      return;
    }
    if (!metrics.model_ready && sendMode !== 'image' && !snapshot?.cloud_route?.available) {
      setModal('library');
      if(voice)throw new Error(t('Дождитесь готовности модели. Голосовая запись сохранена.'));
      return;
    }
    if (sendMode === 'image' && !images.ready && !snapshot?.auto_route?.enabled) {
      setModal('library');
      return;
    }
    setError('');
    setSending(true);
    const message = draftText.trim() || (draftFiles.some(f => f.mime.startsWith('image/')) ? t("Проанализируй прикреплённое изображение.") : t("Изучи прикреплённые файлы."));
    const selectedFiles = [...draftFiles];
    try {
      let id = active.current;
      if (!id) {
        const created = await api('/sessions', {
          method: 'POST',
          body: JSON.stringify({
            cwd: project || boot.default_project,
            mode:sendMode,
            reasoning: voiceQuestion||sendMode==='code'?'none':thinkingLevel,
            access
          })
        });
        id = created.id;
        if(voice&&active.current)throw new Error(t('Чат изменился. Вернитесь в исходный чат или вставьте расшифровку вручную.'));
        active.current = id;
        setSid(id);
        setSnapshot(created.snapshot);
        localStore.setItem('freedom-last-chat', id);
      }
      if(voice){voice.context.sid=id;voice.context.chatKey=id;await voice.bind(id)}
      else{setText('');setFiles([])}
      if(!wasBusy)setOptimistic({
        role: 'user',
        content: message,
        files: selectedFiles
      });
      setBusy(true);
      if(!wasBusy)setLive('');
      autoScroll.current = true;
      const fileIds = selectedFiles.map(f => f.id),
        fingerprint = JSON.stringify([id, message, fileIds, sendMode,isNote,thinkingLevel,webSearch,researchBrowser,researchEngine]);
      if (!voice&&pendingSend.current?.fingerprint !== fingerprint) pendingSend.current = {
        fingerprint,
        input_id: crypto.randomUUID()
      };
      const receipt=await api('/sessions/' + id + (isNote?'/notes':'/messages'), {
        method: 'POST',
        body: JSON.stringify({
          text: message,
          files: fileIds,
          mode:sendMode,
          web_search:webSearch&&sendMode!=='image',
          web_browser:researchBrowser,search_engine:researchEngine,
          reasoning: voiceQuestion||sendMode==='code'?'none':thinkingLevel,
          input_id: voice?'voice_'+voice.id:pendingSend.current.input_id,
          ...(voice?{voice_id:voice.id}:{}),
          ...(voice?.jarvis?{jarvis:voice.jarvis}:window.__freedomJarvisActive&&assistantPrefs.assistant==='tars'?{jarvis:assistantOptions(assistantPrefs)}:{})
        })
      });
      if(receipt.recovered||receipt.state==='recovered')notify(t('Чат продолжен с вашего нового указания'));
      else if(isNote)notify(receipt.state==='steering'?t('Поправка принята для текущей задачи'):t('Поправка сохранена и будет обработана следующей'));
      else if(wasBusy)notify(t('Задание добавлено в очередь'));
      if(!voice){pendingSend.current = null;localStore.removeItem('freedom-draft:new')}
      await loadChat(id, {
        quiet: true
      });
      await refreshSessions();
      return {...receipt,session_id:id};
    } catch (e) {
      if(voice){
        if(voice.context.sid&&active.current===voice.context.sid){
          setOptimistic(null);
          await loadChat(voice.context.sid,{quiet:true});
        }
        throw e;
      }
      setError(e.code==='web_search_unavailable'?e.message:e.message + t(" Если связь прервалась после отправки, проверьте историю перед повтором."));
      if(!wasBusy)setBusy(false);
      setText(message);
      setFiles(selectedFiles);
    } finally {
      setSending(false);
    }
  }
  async function stopTurn(options={}) {
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
      if(options.requireReceipt)throw e;
    }
  }
  function openPreview(url){previewWindow.open(url);setInspector(false);if(window.innerWidth<1100)setCollapsed(true)}
  async function ensureMediaChat(kind){
    if(active.current)return active.current;
    const result=await api('/sessions',{method:'POST',body:JSON.stringify({title:kind==='enhance'?t('Улучшение медиа'):kind==='video'?t('Генерация видео'):kind==='music'?t('Генерация музыки'):kind==='voice'?t('Дикторская озвучка'):t('Генерация изображений'),cwd:project,access,mode:'code'})});
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
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }
  async function trashChat(id,restore=false){
    setDeletingChat(true);
    try{
      await api('/sessions/'+id+'/trash',{method:'POST',body:JSON.stringify({restore})});
      setChatMenu(null);setModal(null);
      if(!restore&&active.current===id)newChat();
      await refreshSessions();
      notify(restore?'Чат восстановлен':'Чат удалён в корзину');
      if(restore){setShowTrash(false);setShowArchive(false);selectChat(id)}
    }catch(e){setError(e.message)}finally{setDeletingChat(false)}
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
    setAccess(value);localStore.setItem('freedom-access',value);
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
      id=created.id;active.current=id;setSid(id);setSnapshot(created.snapshot);localStore.setItem('freedom-last-chat',id);result={status:'selected'};
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
  async function assignSpecialistTask(text,input_id){
    if(!connected)throw new Error(CONNECTION_ERROR);
    if(!metrics.model_ready&&!snapshot?.cloud_route?.available)throw new Error(t('Дождитесь готовности модели.'));
    let id=snapshot?.specialist_chat?.parent_id||active.current;
    if(!id){
      const created=await api('/sessions',{method:'POST',body:JSON.stringify({cwd:project||boot.default_project,mode:'code',access,title:'ИИ Агенты'})});
      id=created.id;active.current=id;setSid(id);setSnapshot(created.snapshot);localStore.setItem('freedom-last-chat',id);
    }
    const receipt=await api('/sessions/'+id+'/messages',{method:'POST',body:JSON.stringify({text,mode:'code',reasoning:'none',web_search:false,input_id:'team_'+input_id})});
    await loadChat(id,{quiet:true});await refreshSessions();setModal(null);notify('Поручение передано основному агенту');
    return receipt;
  }
  async function openSpecialistChat(specialist){
    if(!connected)throw new Error(CONNECTION_ERROR);
    let parent=active.current;
    if(!parent){
      const created=await api('/sessions',{method:'POST',body:JSON.stringify({cwd:project||boot.default_project,mode:'code',access,title:'ИИ Агенты'})});
      parent=created.id;active.current=parent;setSid(parent);setSnapshot(created.snapshot);localStore.setItem('freedom-last-chat',parent);
    }
    const result=await api('/team-agents/chats',{method:'POST',body:JSON.stringify({parent_id:parent,specialist})});
    await refreshSessions();setModal(null);selectChat(result.id);
  }
  const images = metrics.images || boot?.images || {
    percent: 0,
    ready: false,
    files: []
  };
  const selected = sessions.find(s => s.id === sid);
  const filtered = sessions.filter(s => (showTrash?Boolean(s.deleted):!s.deleted&&Boolean(s.archived)===showArchive) && (!search || s.title.toLowerCase().includes(search.toLowerCase())));
  const messages = (chatHistory.messages || snapshot?.messages || []).filter(m => ['user', 'assistant', 'tool'].includes(m.role) && m.display_kind !== 'hidden' && m.display_kind !== 'internal_notification');
  const savedQuestion=snapshot?.work_active?.text;
  const showSavedQuestion=busy&&!optimistic&&!chatHistory.page?.has_newer&&savedQuestion&&!messages.some(m=>m.role==='user'&&getText(m.content).startsWith(savedQuestion));
  const workUsage=snapshot?.work_usage||{};
  const cloudRoute=snapshot?.cloud_route;
  const autoRoute=snapshot?.auto_route,modelLabel=autoRoute?.enabled?t('Авто')+' · '+(autoRoute.current?.name||t('Выбор модели')):snapshot?.local_route?.name||null;
  const displaySpeed=cloudRoute?cloudRoute.stats?.tokens_per_second:metrics.model_ready?metrics.tokens_per_second:null;
  const usage = workUsage.context_tokens>0?workUsage.context_tokens:(!sid||busy?metrics.context_used:null),
    contextMax = cloudRoute?.context_length || (snapshot?.local_route?.loaded?metrics.context_max:null) || snapshot?.local_route?.context_length || workUsage.context_length || metrics.context_max || boot?.context || 65536,
    contextPercent = usage ? Math.min(100, usage / contextMax * 100) : 0;
  const nativeContext=snapshot?.local_route?.native_context||cloudRoute?.context_length||contextMax;
  const contextTooltip=t('Рабочий контекст')+': '+number(contextMax)+' · '+t('Предел модели')+': '+number(nativeContext);
  const videoActivity=useVideoActivity(connected&&Boolean(metrics.gateway_ready)&&!cloudRoute&&!metrics.model_ready&&metrics.local_model_activity===undefined);
  const connection=connectionStatus(connected,{...metrics,local_model_activity:metrics.local_model_activity??videoActivity},cloudRoute);
  return <div className={'app ' + (collapsed ? 'sidebar-collapsed' : '') + (inspector ? ' inspector-open' : '')} onDragOver={e => {
    e.preventDefault();
  }} onDrop={e => {
    e.preventDefault();
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }}>
  <aside className="sidebar" inert={collapsed}>
   <div className="brand"><SidebarBrand tagline={t('ИИ-агент')}/><button className={'icon-button sidebar-search-toggle '+(searchOpen?'active':'')} title={t('Поиск по чатам')+' · Ctrl K'} aria-label={t('Поиск по чатам')} aria-expanded={searchOpen} aria-controls="sidebar-chat-search" onClick={()=>{if(searchOpen)setSearch('');setSearchOpen(v=>!v)}}><Search size={16}/></button><button className="icon-button collapse-button" title={t("Свернуть боковую панель")} onClick={() => setCollapsed(true)}><PanelLeftClose size={17} /></button></div>
   {searchOpen&&<div className="sidebar-search" id="sidebar-chat-search"><Search size={14}/><input ref={sidebarSearch} aria-label={t('Поиск по названиям чатов')} placeholder={t('Найти чат…')} value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==='Escape'){setSearch('');setSearchOpen(false)}if(e.key==='Enter'&&filtered.length===1)selectChat(filtered[0].id)}}/><button className="icon-button" aria-label={t('Закрыть поиск')} onClick={()=>{setSearch('');setSearchOpen(false)}}><X size={13}/></button></div>}
   <nav className="primary-nav"><button className="new-chat" onClick={newChat}><Plus size={18}/><span>{t("Новый чат")}</span><kbd>Ctrl ⇧ O</kbd></button><details className="nav-extras"><summary><MoreHorizontal size={17}/><span>{t("Дополнительно")}</span><ChevronDown size={13}/></summary><div className="nav-extras-menu">
    <button onClick={()=>setModal('team-agents')}><UserRound size={15}/><span>ИИ Агенты</span></button>
    <button className={mode==='code'?'nav-active':''} onClick={()=>{setMode('code');textarea.current?.focus()}}><Code2 size={17}/><span>{t("Код — быстро")}</span></button>
    <button onClick={()=>setModal('skills')}><BookOpen size={15}/><span>{t("Навыки и обучение")}</span></button>
    <button onClick={()=>openPreview()}><Globe size={15}/><span>{t("Просмотр сайта")}</span></button>
    <button className={mode==='image'?'nav-active':''} onClick={()=>{setMode('image');textarea.current?.focus();if(!images.ready&&!snapshot?.auto_route?.enabled)setModal('library')}}><ImagePlus size={17}/><span>{t("Создать изображение")}</span><span className={'tiny-dot '+(images.ready?'green':'amber')}/></button>
    <button onClick={()=>setModal('video')}><Video size={17}/><span>{t("Создать видео")}</span></button>
    <button onClick={()=>setModal('music')}><Music2 size={17}/><span>{t("Музыка и голос")}</span></button>
    {boot?.camera_studio&&<button onClick={()=>setModal('camera-studio')}><Camera size={15}/><span>{t('Камера и аватар')}</span></button>}
    <button onClick={()=>setModal('model-search')}><Search size={15}/><span>{t("Найти нейросеть")}</span></button>
    <button onClick={()=>setModal('hardware-advisor')}><Cpu size={15}/><span>{t("Подбор моделей под ПК")}</span></button>
    <button onClick={()=>setModal('accounts')}><UserRound size={15}/><span>{t('Аккаунты и подключения')}</span></button>
    <button onClick={()=>setModal('api')}><Cloud size={15}/><span>{t("Подключить по API")}</span></button>
    {boot?.converter?.enabled&&<button onClick={()=>setModal('converter')}><ArrowRightLeft size={15}/><span>Конвертер файлов</span></button>}
    <button onClick={()=>setModal('rewards')}><Trophy size={15}/><span>{t('Награды Freedom')}</span></button>
    <button onClick={()=>setModal('vr-workspace')}><Monitor size={15}/><span>VR-пространство</span></button>
    {boot?.arcade?.available&&<button className="arcade-nav-button" onClick={()=>setModal('arcade')}><Gamepad2 size={17}/><span>Игры</span><small className="arcade-mini-label">ARCADE</small></button>}
   </div></details></nav>
   <div className="sidebar-section"><div className="section-heading"><span>{t("Проекты")}</span><button className="icon-button" title={t("Выбрать проект")} onClick={chooseProject}><Plus size={14} /></button></div><button className="project-row" onClick={chooseProject}><Folder size={16} /><span>{shortPath(project)}</span><ChevronRight size={13} /></button></div>
   <div className="chat-heading"><button onClick={() => {setShowTrash(false);setShowArchive(v => !v)}}>{showTrash?t('Корзина'):showArchive ? t("Архив") : t("Недавние")}<ChevronDown size={13} /></button><div className="chat-list-tools"><span>{filtered.length}</span><button className={'icon-button '+(showTrash?'active':'')} aria-label={showTrash?t('Показать недавние чаты'):t('Корзина чатов')} title={showTrash?t('Показать недавние чаты'):t('Корзина чатов')} onClick={()=>{setShowTrash(v=>!v);setShowArchive(false)}}><Trash2 size={13}/></button></div></div>
   <div className="chat-list">{filtered.map(chat => <div key={chat.id} className={'chat-row ' + (sid === chat.id ? 'selected' : '')}><button className="chat-select" onClick={() => selectChat(chat.id)}>{chat.pinned ? <Pin size={13} /> : chat.branch?<GitBranch size={14}/>:<MessageSquare size={14} />}<span className="chat-title-date"><span>{chat.title}</span><time>{formatTime(chat.created||chat.started_at||chat.updated)}</time></span>{chat.running && <span className="tiny-dot green pulse" />}</button><button className="chat-more icon-button" aria-label={t("Действия: ") + chat.title} aria-expanded={chatMenu===chat.id} onClick={() => setChatMenu(chatMenu === chat.id ? null : chat.id)}><MoreHorizontal size={16} /></button>{chatMenu === chat.id && <div className="chat-menu">{chat.deleted?<button disabled={deletingChat} onClick={()=>trashChat(chat.id,true)}><RotateCcw size={14}/>{t('Восстановить')}</button>:<><button disabled={chat.running||branchCreating} title={chat.running?t("Дождитесь завершения ответа и очереди"):t("Продолжить историю в новом чате")} onClick={()=>beginBranch(chat)}><GitBranch size={14}/>{t("Создать ветку")}</button><button onClick={() => {
              setRename(chat.title);
              setModal({
                rename: chat.id
              });
              setChatMenu(null);
            }}><FileText size={14} />{t("Переименовать")}</button><button onClick={() => updateChat(chat.id, {
              pinned: !chat.pinned
            })}><Pin size={14} />{chat.pinned ? t("Открепить") : t("Закрепить")}</button><button onClick={() => updateChat(chat.id, {
              archived: !chat.archived
            })}><Archive size={14} />{chat.archived ? t("Вернуть из архива") : t("В архив")}</button><button className="chat-delete-action" disabled={chat.running} title={chat.running?t('Дождитесь окончания ответа'):t('Удалить чат')} onClick={()=>{setChatMenu(null);setModal({deleteChat:chat})}}><Trash2 size={14}/>{t('Удалить чат')}</button></>}</div>}</div>)}{!filtered.length && <p className="empty-list">{search?t('Чаты не найдены'):showTrash?t('Корзина пуста'):showArchive ? t("В архиве пока пусто") : t("Здесь появятся ваши чаты")}</p>}</div>
   <div className="sidebar-bottom"><div className="sidebar-tools" role="group" aria-label={t("Локальные модели") + ' · ' + t("Настройки")}><button type="button" className="sidebar-models" onClick={() => setModal('library')} title={t("Выбор, загрузка и переключение")}><HardDrive size={16} /><span>{t("Локальные модели")}</span><ChevronRight size={13} /></button><button type="button" className="sidebar-settings" onClick={() => setModal('settings')} title={t("Настройки")} aria-label={t("Настройки")}><Settings size={16} /></button>{!images.ready && <div className="sidebar-download-progress" aria-hidden="true"><i style={{
              width: images.percent + '%'
            }} /></div>}</div></div>
  </aside>
  <main className={'main'+(!sid&&!neuroVisible?' welcome-main':'')}>
   <header className="topbar"><div className="topbar-title">{collapsed && <button className="icon-button" title={t("Показать чаты")} onClick={() => setCollapsed(false)}><PanelLeft size={19} /></button>}<span>{sid ? selected?.title || t("Чат") : t("Рабочее пространство")}</span>{sid && <span className="saved-indicator" title={t("История хранится локально")}><CheckCheck size={14} /></span>}</div><NeuroViewSwitch mode={neuroMode} visible={neuroVisible} onChange={changeNeuroView}/><div className="topbar-actions"><MessengerButton/><LocaleSwitch />{sid&&<button className="icon-button" title={t("История и поиск в этом чате")} aria-label={t("История и поиск в этом чате")} onClick={()=>setModal('chat-history')}><History size={16}/></button>}<span className={'connection ' + (connection.ready ? 'is-ready' : '')} title={connection.hint?t(connection.hint):undefined}><i />{t(connection.label)}</span><button className={"icon-button preview-open-button "+(previewOpen?"active":"")} aria-label={t("Просмотр сайта")} title={t("Просмотр сайта")} onClick={()=>previewOpen?previewWindow.close():openPreview()}><PanelRightOpen size={17}/></button><button className={'monitor-toggle ' + (inspector ? 'active' : '')} onClick={() => setInspector(v => !v)} title={t("Вычисления и скорость")}><Activity size={15} /><span>{displaySpeed ? displaySpeed.toFixed(1) + t(" ток/с") : cloudRoute?t("API"):t("Вычисления")}</span></button><TurboControl control={turbo} compact cloud={Boolean(cloudRoute)}/><button className="icon-button" title={t("Настройки")} onClick={() => setModal('settings')}><SlidersHorizontal size={17} /></button></div></header>
   {neuroVisible&&<NeuroBoundary onClose={()=>changeNeuroView('chat')}><React.Suspense fallback={<div className="neuro-loading-shell">Загружаю Нейросферу…</div>}><Neurosphere onDevelopment={seed=>{setDevelopmentSeed(seed);setModal('development')}} onThink={thinkFromNeurosphere} unavailable={sending||loadingChat||!!uploading} sid={sid} snapshot={snapshot||{}} busy={busy} gpu={metrics.gpu} onChat={id=>{selectChat(id);changeNeuroView('chat')}} onProject={path=>{if(sid)newChat();setProject(path);changeNeuroView('chat')}} onMemory={()=>setModal('project-memory')} onSkills={()=>setModal('skills')} onGoal={openGoal} onClose={()=>changeNeuroView('chat')}/></React.Suspense></NeuroBoundary>}
   <div className={'conversation ' + (neuroVisible?'neuro-hidden ':'') + (!sid ? 'welcome-view' : '')} ref={scroll} onScroll={e => {
        const el = e.currentTarget;
        autoScroll.current = el.scrollHeight - el.scrollTop - el.clientHeight < 120;
      }}>
    {sid&&autoRoute?.enabled&&<div className="auto-route-status"><Sparkles size={13}/><span>{t('Авто')} · {roleName(autoRoute.role)} · {autoRoute.current?.name||t('Выбор модели')}</span><button onClick={()=>setModal('chat-model')}>{t('Настроить')}</button></div>}
    {!sid ? <div className="welcome"><WelcomeBrand key={welcomeGeneration}/><div className="eyebrow">{t("ВАШ ИИ-АГЕНТ. ВАШ КОМПЬЮТЕР.")}</div><h1>{t("Что создадим сегодня?")}</h1></div> : <div className="messages">
     {selected?.deleted&&<div className="chat-trash-notice"><Trash2 size={15}/><span>{t('Чат в корзине. История доступна для просмотра.')}</span><button disabled={deletingChat} onClick={()=>trashChat(sid,true)}>{t('Восстановить')}</button></div>}
     {snapshot?.specialist_chat&&<SpecialistChatHeader key={sid} sid={sid} binding={snapshot.specialist_chat} messages={messages} onMain={selectChat} onSettings={()=>setModal('team-agents')}/>}
     <div className="conversation-context"><Folder size={13}/><button onClick={chooseProject}>{shortPath(project)}</button><span>·</span><button className="conversation-model" onClick={()=>setModal('chat-model')}>{modelLabel||cloudRoute?.name||snapshot?.info?.model||boot?.model||t("Выберите модель")}</button><button className="conversation-branch-button" aria-label={t("Создать ветку чата")} title={busy?t("Дождитесь завершения ответа и очереди"):t("Создать ветку чата")} disabled={busy||loadingChat||branchCreating} onClick={()=>beginBranch(selected||{id:sid,title:snapshot?.info?.title||t("Чат")})}><GitBranch size={13}/></button></div><div className="conversation-created"><Clock3 size={12}/><span>{t("Чат создан")} {formatTime(snapshot?.info?.started_at||selected?.created||selected?.started_at)}</span><span>·</span><span>{t("История и память сохраняются локально")}</span>{sid&&<button className="project-memory-link" onClick={()=>setModal('project-memory')} title={t("Поиск в памяти проекта")}><BookOpen size={11}/>{t("Память")}</button>}{!!snapshot?.notes?.length&&<button className="notes-history-link" onClick={()=>setModal('notes-history')} title={t("История поправок")}><History size={11}/>{t("Поправки")} · {snapshot.notes.length}</button>}</div>
     <HistoryPaging history={chatHistory}/>
     <BranchOrigin branch={snapshot?.branch||selected?.branch} onOpen={selectChat}/>
     {snapshot?.progress_guard_notice&&<div className="loop-guard-notice" role="status"><ShieldCheck size={15}/><span><strong>{t('Повторения остановлены')}</strong><small>{t('Агент повторял действия без нового результата. История и файлы сохранены.')} {snapshot.progress_guard_notice.tool}</small></span></div>}
     {loadingChat ? <div className="loading-chat"><LoaderCircle size={18} className="spin" />{t("Загружаем сохранённый чат…")}</div> : messages.map((message, index) => {
            const replyId=messageKey(message)||'reply-'+index;
            const loopStopped=!chatHistory.page?.has_newer&&guardStoppedReply(message,index,messages.length,snapshot?.progress_guard_notice);
            const content = loopStopped?t('Повтор без продвижения остановлен. Задача пока не завершена; история и выполненные шаги сохранены.'):message.is_checkpoint?t('История чата сжата. Полная запись сохранена на диске; агент может восстановить детали из памяти проекта и истории.'):(message.role==='assistant'?serviceMessage(getText(message.content),getLocale()):message.role==='user'?userMessage(getText(message.content)):getText(message.content));
            if(message.display_kind==='async_delegation_complete')return <TeamCompletion key={messageKey(message)||index} message={message}/>;
            if(message.role==='user'&&content.startsWith('[CONTEXT COMPACTION'))return <details className="context-memory-note" key={message.message_uid||index}><summary><BookOpen size={13}/>{t('Память чата после сжатия')}<ChevronRight size={13}/></summary><pre>{content}</pre></details>;
            if (message.role === 'tool') return <HistoryTool key={messageKey(message)||index} message={message} messages={messages}/>;
            if (!content.trim()) return null;
            const attached = message.role === 'user' ? snapshot?.attachments?.find(t => content.includes(t.text.slice(0, 100))) : null;
            return <article id={'history-message-'+messageKey(message)} className={'message ' + message.role+(chatHistory.highlight===messageKey(message)?' history-highlight':'')} key={messageKey(message) || index}>
       {message.role === 'assistant' && <div className="assistant-avatar"><img src="/freedom.svg" alt="" /></div>}
       <div className="message-body">{message.role === 'assistant' && <div className="message-byline">Freedom GPT</div>}
        {attached && <div className="message-attachments">{attached.files.map(file => <a href={'/api/files/' + file.id} key={file.id} target="_blank" rel="noreferrer">{file.mime.startsWith('image/') ? <img src={'/api/files/' + file.id} alt={file.name} /> : <FileText size={20} />}<span>{file.name}</span></a>)}</div>}
        {message.role === 'user' ? <div className="user-text"><Inline text={attached?.text || content} files={snapshot?.artifacts||[]} onPreview={openPreview}/></div> : <><Markdown text={content} files={snapshot?.artifacts||[]} onPreview={openPreview}/><MediaCards files={referencedMedia(content,snapshot?.artifacts||[])}/></>}
        <div className="message-actions"><CopyButton text={message.role === 'user' ? attached?.text || content : content} label={message.role === 'user' ? t("Копировать сообщение") : t("Копировать")} />{message.role==='assistant'&&boot?.speech?.enabled&&<ReadAloudButton text={content} id={replyId}/>}{message.role==='assistant'&&!message.is_checkpoint&&<SaveReplySkill key={(sid||'')+':'+replyId} Modal={Modal} text={content} sessionId={sid} messageId={replyId} files={snapshot?.artifacts||[]} onSaved={notify}/>}<BookmarkMessage message={message} onClick={()=>chatHistory.bookmark(message)}/></div><MessageTiming message={message} stopped={loopStopped} onBranch={message.role==='assistant'&&!message.is_checkpoint?()=>beginBranch(selected||{id:sid,title:snapshot?.info?.title||t('Чат')}):undefined} branchDisabled={busy||loadingChat||branchCreating}/>
       </div>
      </article>;
          })}
     {chatHistory.page?.has_newer&&<div className="history-bottom-return"><button type="button" onClick={chatHistory.latest}>{t("К последним сообщениям")}</button></div>}
     {showSavedQuestion&&<article className="message user"><div className="message-body"><div className="user-text"><Inline text={savedQuestion} files={snapshot?.artifacts||[]} onPreview={openPreview}/></div><MessageTiming message={{timestamp:snapshot.work_active.submitted_at||snapshot.work_active.created}}/></div></article>}
     {optimistic && <article className="message user"><div className="message-body"><div className="user-text">{optimistic.content}</div></div></article>}
     <ActivityMessage key={'activity-'+(sid||'no-chat')} sid={sid} activity={snapshot?.activity} history={snapshot?.messages||[]} busy={busy} live={live} tool={tool} started={snapshot?.work_active?.started||snapshot?.work_active?.created||snapshot?.live?.started_at}>{live ? <Markdown text={live} files={snapshot?.artifacts||[]} onPreview={openPreview}/> : null}</ActivityMessage>
     {snapshot?.prompts?.map(prompt => <PromptCard key={prompt.prompt_id} prompt={prompt} onAnswer={answer => answerPrompt(prompt, answer)} />)}
     {!!snapshot?.pending?.some(p => p.status === 'unknown') && <div className="chat-recovery-notice" role="status"><AlertCircle size={16} /><div><strong>{t('Одно из действий прервано — чат можно продолжить')}</strong><p>{t('Часть изменений могла сохраниться. Новое указание или поправка из очереди будут обработаны первыми.')}</p></div><button onClick={()=>textarea.current?.focus()}>{t('Написать поправку')}</button></div>}
     <UnreferencedMedia files={snapshot?.artifacts||[]} messages={messages}/>
     <ChatFiles key={'files-'+sid} files={snapshot?.artifacts||[]} trash={snapshot?.artifact_trash||[]} Modal={Modal} notify={notify} onChanged={()=>refreshChatFiles(sid)}/>
    </div>}
   </div>
   <ChatScrollToBottom scroll={scroll} autoScroll={autoScroll} sid={sid} hidden={neuroVisible} history={chatHistory}/>
   <div className="composer-zone">{boot?.speech?.enabled&&<SpeechPlayer/>}<QueuePanel key={sid||'new'} items={snapshot?.queue||[]} notes={snapshot?.notes||[]} busy={busy} interrupted={!!snapshot?.pending?.some(p=>p.status==='unknown')} onAction={queueAction}/>
    {(recovering || !connected) && <div className="connection-banner" role="status"><RefreshCw size={14} className="spin" /><span>{t("Восстанавливаем связь с локальной панелью. Черновик сохранён.")}</span><button onClick={() => window.dispatchEvent(new Event('freedom-reconnect'))}>{t("Проверить связь")}</button></div>}
    {error && <div role="alert" className="error-banner"><AlertCircle size={16} /><span>{t(error)}</span><button className="icon-button" aria-label={t("Скрыть ошибку")} onClick={() => setError('')}><X size={14} /></button></div>}
    <div className="composer-wrap">{sid&&chatHistory.page?.has_newer&&<div className="history-return-latest"><button type="button" disabled={chatHistory.working} onClick={chatHistory.latest}><ArrowDown size={12}/>{t("К последним сообщениям")}</button></div>}{!busy&&<div className="composer-mode-row"><div className="mode-switch" role="group" aria-label={t("Режим работы")}><button disabled={busy || sending} className={mode === 'code' ? 'selected' : ''} aria-pressed={mode === 'code'} onClick={() => setMode('code')} title={t("Прямой ответ без отдельного обдумывания. Для сложной логики используйте «Обдумать» и проверку тестами.")}><Code2 size={13} />{t("Код — быстро")}</button><button disabled={busy || sending} className={mode === 'chat' ? 'selected' : ''} aria-pressed={mode === 'chat'} onClick={() => {setMode('chat');setThinkingLevel(v=>v==='none'?'medium':v)}} title={t("Дополнительное обдумывание сложной задачи перед ответом.")}><Sparkles size={13} />{t(['high','xhigh'].includes(thinkingLevel)?"Глубоко":thinkingLevel==='medium'?"Стандартно":"Обдумать")}</button><button className="thinking-settings-open" onClick={()=>setModal('run-settings')} title={t("Контекст и обдумывание")}><SlidersHorizontal size={12}/></button></div></div>}
    <div className="workspace-strip"><div className="workspace-context"><button onClick={chooseProject}><Folder size={13} /><span>{shortPath(project)}</span><ChevronDown size={12} /></button><span className="workspace-local"><Monitor size={13} />{t("Этот компьютер")}</span></div><div className="workspace-actions"><GoalButton state={snapshot?.goal_state} busy={busy} onClick={openGoal}/><Jarvis onNewChat={newChat} settingsOpen={modal==='settings'} onOpenSettings={()=>{setModal('settings');setTimeout(()=>document.getElementById('jarvis-settings')?.scrollIntoView({block:'start',behavior:'smooth'}),80)}} available={boot?.voice} speechInfo={boot?.speech} sid={sid} busy={busy} snapshot={snapshot} live={live} disabled={loadingChat||sending||!!uploading} getContext={()=>({sid:active.current,chatKey:active.current||'new',mode,project})} onTask={(value,intent)=>send(intent||'queue',value)} onStop={()=>stopTurn({requireReceipt:true})} onQueue={()=>{textarea.current?.focus();document.querySelector('.composer-zone')?.scrollIntoView({block:'end',behavior:'smooth'})}} onStatus={()=>{textarea.current?.focus();notify(busy?t('Агент выполняет задачу. Ход работы виден в чате.'):t('В этом чате нет активной задачи.'))}}/><ResearchButtons working={busy} sid={sid} browser={researchBrowser} engine={researchEngine} onSelection={researchSelection} web={webSearch} image={mode==='image'} sending={sending} onWeb={()=>{setWebSearch(value=>!value);if(mode==='image')setMode('code');textarea.current?.focus()}} onImage={()=>{setWebSearch(false);setMode('image');if(!images.ready&&!snapshot?.auto_route?.enabled)setModal('library')}}/>{mode === 'image' && <button type="button" className="image-mode-close" title={t("Выйти из режима изображения")} aria-label={t("Выйти из режима изображения")} onClick={() => setMode('code')}><X size={12} /></button>}</div></div>
     <div className={'composer ' + (mode === 'image' ? 'image-composer' : '')}>
      {!!files.length && <div className="attachment-list">{files.map(file => <div className="attachment-chip" key={file.id} data-freedom-file-id={file.id} data-freedom-file-source="files">{file.mime.startsWith('image/') ? <img src={'/api/files/' + file.id} alt="" /> : <FileText size={20} />}<div><strong>{file.name}</strong><span>{prettyBytes(file.bytes)}</span></div><button className="icon-button" aria-label={t("Убрать ") + file.name} onClick={() => setFiles(v => v.filter(f => f.id !== file.id))}><X size={13} /></button></div>)}</div>}
      <textarea ref={textarea} aria-label={t("Сообщение Freedom GPT")} placeholder={busy?t("Добавить задачу или уточнение…"):mode==='image'?t("Опишите изображение, которое хотите создать…"):t("Поручите что угодно…")} value={text} rows={2} onChange={e => setText(e.target.value)} onKeyDown={e => {
              if (e.key === 'Enter' && !e.nativeEvent.isComposing && busy && e.altKey) {
                e.preventDefault();
                send('steer');
              } else if (e.key === 'Enter' && !e.nativeEvent.isComposing && !e.altKey && (enterSend && !e.shiftKey || !enterSend && (e.ctrlKey || e.metaKey))) {
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
      <div className="composer-footer"><div className="composer-tools"><VoiceInput enabled={boot?.voice?.enabled} ready={boot?.voice?.ready} busy={busy} disabled={loadingChat||sending||!!uploading} getContext={()=>({sid:active.current,chatKey:active.current||'new',mode,project})} onTask={value=>send('queue',value)} onInsert={value=>{setText(current=>current?current+'\n'+value:value);textarea.current?.focus()}}/><button className="icon-button attach-button" aria-label={t("Прикрепить фото или файл")} title={t("Фото, документы и файлы · до 50 МБ")} onClick={() => fileInput.current?.click()}>{uploading ? <LoaderCircle className="spin" size={20} /> : <Plus size={21} />}</button><button className={'access-label access-picker '+(access==='full'?'full':'')} onClick={()=>setModal('access')} title={t("Режим доступа агента")}><ShieldCheck size={13}/>{access==='full'?t("Полный доступ"):t("С подтверждениями")}<ChevronDown size={10}/></button></div><div className="composer-controls"><button className="model-picker" onClick={() => setModal(sid?'chat-model':'library')}>{modelLabel||cloudRoute?.name||snapshot?.info?.model||metrics.active_model_name||boot?.model_short||t("Модель")}<ChevronDown size={12} /></button><button className="composer-context-picker" onClick={()=>setModal('run-settings')} title={t("Контекст и обдумывание")}>{number(contextMax)}<ChevronDown size={10}/></button><ComposerSendActions busy={busy} interrupted={!!snapshot?.pending?.some(p=>p.status==="unknown")} hasContent={!!text.trim()||!!files.length} canSubmit={!sending&&!uploading&&(!!text.trim()||!!files.length)&&connected} canSteer={!files.length} sending={sending} onSend={send} onStop={stopTurn}/></div></div>
     </div>
    </div><div className="composer-caption"><span>{mode === 'image' ? t("Изображения создаются локально. На время генерации видеокарта переключается на Qwen Image.") : busy ? (enterSend ? t("Enter — в очередь · Alt + Enter — скорректировать") : t("Ctrl + Enter — в очередь · Alt + Enter — скорректировать")) : enterSend ? t("Enter — отправить · Shift + Enter — новая строка") : t("Ctrl + Enter — отправить · Enter — новая строка")}</span><button className="compact-usage" title={t("Всего обработано токенов в этом чате")} onClick={()=>setInspector(true)}>Σ {number(workUsage.total_tokens||0)}</button><button title={contextTooltip+' · '+t("Настроить контекст")} onClick={() => setModal('run-settings')}><i className="context-ring" style={{
              '--used': contextPercent + '%'
            }} />{usage ? number(usage) + ' / ' : ''}{number(contextMax)}</button></div>
   </div>
  </main>
  {!previewOpen&&previewWindow.view.finished&&previewWindow.view.latest?.url&&<button className="preview-minimized" onClick={()=>openPreview()}><PanelRightOpen size={14}/><span>{t('Просмотр сайта')}<small>{t('Проверка завершена')}</small></span><ChevronRight size={13}/></button>}
  {previewOpen&&<PreviewBoundary key={sid||'workspace'} onClose={previewWindow.close} onRetry={previewWindow.refresh}><BrowserPreview sid={sid} request={previewRequest} liveState={previewWindow.view.latest} onState={previewWindow.reconcile} onClose={previewWindow.close}/></PreviewBoundary>}
  {inspector && <aside className="inspector"><header><div><Activity size={16} /><strong>{t("Вычисления")}</strong></div><button className="icon-button" aria-label={t("Закрыть панель вычислений")} onClick={() => setInspector(false)}><X size={16} /></button></header><div className="inspector-scroll"><section className="speed-card"><div className="subtle-label">{t("СКОРОСТЬ ГЕНЕРАЦИИ")}</div><div className="big-speed">{displaySpeed ? displaySpeed.toFixed(1) : '—'}<span>{t("токенов/с")}</span></div><div className="speed-state"><i className={'tiny-dot ' + (metrics.processing ? 'green pulse' : 'muted')} />{cloudRoute?(busy?t("Запрос к API"):t("Последний ответ API")):metrics.processing ? metrics.speed_kind === 'live' ? t("Сейчас генерирует") : t("Обрабатывает запрос") : t("Последний ответ")}</div><p>{cloudRoute?t("Скорость последнего ответа API по данным usage. При отсутствии счётчика провайдера показывается прочерк."):t("Показатель из журнала модели, включая токены рассуждений. Чтение контекста считается отдельно.")}</p><TurboControl control={turbo} cloud={Boolean(cloudRoute)}/></section><section><div className="monitor-heading"><Cpu size={14} /><strong>{metrics.gpu?.name?.replace('NVIDIA GeForce ', '') || t("Видеокарта")}</strong><span>{metrics.gpu?.temperature ? metrics.gpu.temperature + ' °C' : '—'}</span></div><Sparkline values={history.gpu} /><Meter label={t("Загрузка GPU")} value={metrics.gpu ? metrics.gpu.percent + '%' : '—'} percent={metrics.gpu?.percent} /><Meter label={t("Видеопамять")} value={metrics.gpu ? (metrics.gpu.used_mb / 1024).toFixed(1) + ' / ' + (metrics.gpu.total_mb / 1024).toFixed(1) + t(" ГБ") : '—'} percent={metrics.gpu ? metrics.gpu.used_mb / metrics.gpu.total_mb * 100 : 0} /><div className="monitor-foot">{t("Потребление ")}<span>{metrics.gpu?.watts ? Math.round(metrics.gpu.watts) + t(" Вт") : '—'}</span></div></section><section><div className="monitor-heading"><Monitor size={14} /><strong>{t("Система")}</strong></div><Sparkline values={history.cpu} color="#8cc9b6" /><Meter label={t("Процессор")} value={metrics.cpu_percent !== undefined ? Math.round(metrics.cpu_percent) + '%' : '—'} percent={metrics.cpu_percent} color="#8cc9b6" /><Meter label={t("Оперативная память")} value={metrics.ram_total ? prettyBytes(metrics.ram_used) + ' / ' + prettyBytes(metrics.ram_total) : '—'} percent={metrics.ram_used / metrics.ram_total * 100} color="#8cc9b6" /></section><section><div className="monitor-heading"><MessageSquare size={14} /><strong>{t("Контекст модели")}</strong></div><Meter label={number(usage) + ' / ' + number(contextMax)} value={usage!=null?contextPercent.toFixed(0)+'%':'—'} percent={contextPercent} /><p className="muted-copy">{t("Предел модели")}: {number(nativeContext)} {t("токенов")}.{snapshot?.local_route&&<><br/>{t(snapshot.local_route.context_mode==='verified'?"Для этой модели выбран проверенный профиль ПК, чтобы сохранить скорость.":"Рабочее окно подбирается по доступной памяти ПК при запуске модели.")}{nativeContext>contextMax&&<><br/>{t("Полное окно этой модели требует больше памяти.")}</>}</>}</p><p className="muted-copy">{t("Автосжатие зависит от выбранной модели. История и память проекта сохраняются локально.")}</p></section><section className="token-totals"><div className="monitor-heading"><ListOrdered size={14}/><strong>{t("Токены этого чата")}</strong></div><div className="total-token-number">{number(workUsage.total_tokens||0)}</div><div className="token-breakdown"><span>{t("Входящие")}<strong>{number(workUsage.input_tokens||0)}</strong></span><span>{t("Сгенерировано")}<strong>{number(workUsage.output_tokens||0)}</strong></span><span>{t("В том числе рассуждения")}<strong>{number(workUsage.reasoning_tokens||0)}</strong></span><span>{t("Запросов к модели")}<strong>{number(workUsage.api_calls||0)}</strong></span><span>{t("Всего во всех чатах")}<strong>{number(Math.max(workUsage.all_chats_tokens||0,workUsage.total_tokens||0))}</strong></span></div><p>{t("Это общий расход за все обращения. Повторное чтение истории считается снова; это не размер контекста.")}</p></section><button className="inspector-model-link" onClick={() => setModal('library')}><HardDrive size={15} /><span>{images.ready ? t("Модели готовы") : t("Загрузка изображений · ") + images.percent + '%'}</span><ChevronRight size={14} /></button></div><footer><span className="tiny-dot green" />{t("API доступен только на этом ПК")}</footer></aside>}
  <SpeechCoordinator available={boot?.speech} sid={sid} snapshot={snapshot} busy={busy}/>
  <EnhanceCoordinator enabled={!!boot?.enhance?.enabled} sid={sid} onEnsureChat={()=>ensureMediaChat('enhance')}/>
  <input ref={fileInput} type="file" multiple className="hidden-input" onChange={e => {
      addFiles(e.target.files);
      e.target.value = '';
    }} />
   <ContextMenu files={[...(snapshot?.artifacts||[]),...(snapshot?.attachments||[]).flatMap(item=>item.files.map(file=>({...file,url:'/api/files/'+file.id,source:'files'}))),...files.map(file=>({...file,url:'/api/files/'+file.id,source:'files'}))]} onPreview={openPreview} notify={notify}/>
   <CompletionNotifications sessions={sessions} onOpen={id=>{setModal(null);selectChat(id)}}/>
   {toast && <div role="status" className="toast"><Check size={15} />{toast}</div>}
  {rewardToast&&<div className="reward-live-toast" role="status"><Trophy size={24}/><button onClick={()=>{setModal('rewards');setRewardToast(null)}}><small>{rewardToast.unlocks?.length?t('Открыта награда'):t('Новый уровень')}</small><strong>{rewardToast.unlocks?.length?(getLocale()==='en'?(rewardToast.unlocks[0].name_en||rewardToast.unlocks[0].name):t(rewardToast.unlocks[0].name)):t('Уровень')+' '+rewardToast.profile.level}</strong></button><button aria-label={t('Закрыть')} onClick={()=>setRewardToast(null)}><X size={13}/></button></div>}
  {modal==='arcade'&&<React.Suspense fallback={<div className="neuro-loading-shell">Открываем игровую…</div>}><ArcadePanel busy={busy} onClose={()=>setModal(null)}/></React.Suspense>}
  {modal==='development'&&<Modal title="Совместное развитие" wide onClose={()=>setModal(null)}><React.Suspense fallback={<p className="panel-intro">Открываем планы развития…</p>}><NeuroDevelopment seed={developmentSeed} fullAccess={access==='full'} onChanged={()=>refreshSessions()} onOpenChat={id=>{setModal(null);selectChat(id);changeNeuroView('chat')}}/></React.Suspense></Modal>}
  {modal==='vr-workspace'&&<React.Suspense fallback={<div className="vr-workspace">Загружаем VR-пространство…</div>}><VRWorkspace snapshot={snapshot} live={live} busy={busy} metrics={metrics} sessions={sessions} onChat={id=>loadChat(id)} onClose={()=>setModal(null)}/></React.Suspense>}
  {modal==='camera-studio'&&<Modal title={t('Камера и аватар')} wide onClose={()=>setModal(null)}><React.Suspense fallback={<p className="panel-intro">{t('Открываем видеостудию…')}</p>}><CameraStudioPanel/></React.Suspense></Modal>}
  {modal==='rewards'&&<Modal title={t('Награды Freedom')} subtitle={t('Ваши идеи становятся результатами. Результаты — вашим прогрессом.')} onClose={()=>setModal(null)} wide><RewardsPanel sid={sid}/></Modal>}
  {modal==='accounts'&&<Modal title={t('Аккаунты и подключения')} subtitle={t('Ваш GitHub, ваши модели. Подключайте только то, что нужно.')} onClose={()=>setModal(null)} wide><AccountConnections onAdvisor={()=>setModal('hardware-advisor')} onLibrary={tab=>setModal({models:{kind:'chat',tab}})}/></Modal>}
  {modal==='hardware-advisor'&&<Modal title={t('Подбор моделей под ваш ПК')} onClose={()=>setModal(null)} wide><HardwareAdvisor onMusic={()=>setModal('music')} onLibrary={(task,tab)=>setModal({models:{kind:['code','chat'].includes(task)?'chat':task,tab,task}})}/></Modal>}
  {(['library','library-video','model-search'].includes(modal)||modal?.models) && <ModelLibrary onAccounts={()=>setModal('accounts')} searchTask={modal?.models?.task} initialKind={modal?.models?.kind||(modal==='library-video'?'video':'all')} initialTab={modal?.models?.tab||(modal==='model-search'||boot?.first_run?'search':'catalog')} onClose={() => setModal(modal==='library-video'?'video':null)} onActivated={() => window.location.reload()} />}
  {(modal==='music'||modal==='music-api')&&<MediaStudio initialSource={modal==='music-api'?'stability':'local'} sid={sid} onEnsureChat={(kind='music')=>ensureMediaChat(kind)} onClose={()=>setModal(null)} onApi={()=>setModal('api-stability')}/>}
  {modal==='video'&&<VideoStudio sid={sid} onEnsureChat={()=>ensureMediaChat('video')} onClose={()=>setModal(null)} onModels={()=>setModal('library-video')} onApi={()=>setModal('api-fal')}/>}
  {modal==='notes-history'&&<Modal title={t("История поправок")} onClose={()=>setModal(null)}><NotesPanel notes={snapshot?.notes||[]} onAction={queueAction}/></Modal>}
  {modal?.branch&&<Modal title={t('Создать ветку чата')} onClose={()=>{if(!branchCreating)setModal(null)}}><BranchDialog key={modal.branch.id} source={modal.branch} onBusy={setBranchCreating} onCreated={branchCreated} onCancel={()=>setModal(null)}/></Modal>}
  {(modal==='api'||modal==='api-fal'||modal==='api-stability')&&<Modal title={t('Подключить по API')} wide onClose={()=>setModal(null)}><ApiConnections onMusic={()=>setModal('music-api')} initialProvider={modal==='api-fal'?'fal':modal==='api-stability'?'stability':''} sid={sid} onEnsureChat={()=>ensureMediaChat(modal==='api-fal'?'video':'image')} busy={busy} onUse={useApiModel}/></Modal>}
  {modal==='project-memory'&&sid&&<Modal title={t('Память проекта')} wide onClose={()=>setModal(null)}><ProjectMemoryPanel sid={sid}/></Modal>}
  {modal==='converter'&&<Modal title="Конвертер файлов" subtitle="Бесплатно · без интернета и внешних сервисов" wide onClose={()=>setModal(null)}><FileConverterPanel sid={sid}/></Modal>}
  {modal==='chat-history'&&sid&&<Modal title={t('История чата')} wide onClose={()=>setModal(null)}><ChatHistoryPanel sid={sid} history={chatHistory} onClose={()=>setModal(null)}/></Modal>}
  {modal==='goal'&&sid&&<Modal title={t("Цель проекта")} wide onClose={()=>setModal(null)}><GoalPanel key={sid} sid={sid} state={snapshot?.goal_state} workBusy={busy||!!snapshot?.queue?.length} onChanged={state=>{setSnapshot(value=>value?{...value,goal_state:state}:value);loadChat(sid,{quiet:true});refreshSessions()}}/></Modal>}
  {modal==='access'&&<Modal title={t("Режим доступа")} onClose={()=>setModal(null)}><AccessPanel value={access} onChange={changeAccess} onClose={()=>setModal(null)}/></Modal>}
  {modal==='run-settings'&&<Modal title={t('Контекст и обдумывание')} subtitle={t('Подберите режим под задачу и возможности ПК')} onClose={()=>setModal(null)}><RunSettings sid={sid} cloud={Boolean(cloudRoute)} agentBusy={busy} reasoning={mode==='code'?'none':thinkingLevel} onReasoning={value=>{setThinkingLevel(value);setMode(value==='none'?'code':'chat')}} onChanged={()=>{if(sid)loadChat(sid,{quiet:true})}}/></Modal>}
  {modal==='chat-model'&&<Modal title={t("Модель этого чата")} onClose={()=>setModal(null)}><ChatModelPanel onRunSettings={()=>setModal('run-settings')} onApi={()=>setModal('api')} sid={sid} current={snapshot?.info?.model} onChanged={async()=>{await loadChat(sid,{quiet:true});setModal(null);notify(t("Модель переключена. История сохранена."))}} onLibrary={()=>setModal('library')}/></Modal>}
  {modal==='team-agents'&&<Modal title="ИИ Агенты" wide onClose={()=>setModal(null)}><TeamAgentsPanel sid={sid} initialRole={snapshot?.specialist_chat?.specialist_id} onTask={assignSpecialistTask} onChat={openSpecialistChat}/></Modal>}
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
    }}><div className="modal-search"><Search size={16} /><input autoFocus placeholder={t("Название или тема чата…")} value={search} onChange={e => setSearch(e.target.value)} /></div><div className="search-results">{sessions.filter(s => !s.deleted&&s.title.toLowerCase().includes(search.toLowerCase())).map(chat => <button key={chat.id} onClick={() => {
          selectChat(chat.id);
          setModal(null);
          setSearch('');
        }}><MessageSquare size={16} /><span>{chat.title}</span><ChevronRight size={14} /></button>)}</div></Modal>}
  {modal?.deleteChat&&<Modal title={t('Удалить чат?')} onClose={()=>{if(!deletingChat)setModal(null)}}><p className="panel-intro">«{modal.deleteChat.title}» {t('переместится в корзину и исчезнет из списка чатов. Его можно будет восстановить.')}</p><div className="modal-buttons"><button disabled={deletingChat} onClick={()=>setModal(null)}>{t('Отмена')}</button><button className="primary-button" disabled={deletingChat} onClick={()=>trashChat(modal.deleteChat.id)}><Trash2 size={14}/> {deletingChat?t('Удаляем…'):t('Удалить чат')}</button></div></Modal>}
  {modal?.rename && <Modal title={t("Переименовать чат")} onClose={() => setModal(null)}><form onSubmit={async e => {
        e.preventDefault();
        const saved=await updateChat(modal.rename, {
          title: rename
        });
        if(saved)setModal(null);
      }}><input className="full-input" aria-label={t("Название чата")} autoFocus value={rename} onChange={e => setRename(e.target.value)} maxLength={160} /><div className="modal-buttons"><button type="button" onClick={() => setModal(null)}>{t("Отмена")}</button><button className="primary-button" type="submit" disabled={!rename.trim()}>{t("Сохранить")}</button></div></form></Modal>}
  {modal === 'phone-access' && <Modal title={t('Доступ с телефона')} wide onClose={()=>setModal(null)}><RemoteAccessPanel/></Modal>}
  {modal === 'settings' && <Modal title={t("Настройки Freedom GPT")} subtitle={t("Ваше личное рабочее пространство")} headerActions={<><LocaleSwitch/><div className="segmented settings-theme-switch" role="group" aria-label={t("Оформление")}><button type="button" className={theme === 'dark' ? 'active' : ''} aria-pressed={theme === 'dark'} aria-label={t("Тёмная тема")} title={t("Тёмная тема")} onClick={()=>setTheme('dark')}><Moon size={14}/></button><button type="button" className={theme === 'light' ? 'active' : ''} aria-pressed={theme === 'light'} aria-label={t("Светлая тема")} title={t("Светлая тема")} onClick={()=>setTheme('light')}><Sun size={14}/></button></div></>} onClose={() => setModal(null)}><Preferences jarvisEnabled={!!boot?.voice?.enabled} speechInfo={boot?.speech} voiceEnabled={!!boot?.speech?.enabled} onConverter={boot?.converter?.enabled?()=>setModal('converter'):null} onPhone={()=>setModal('phone-access')} onAdvisor={()=>setModal('hardware-advisor')} onAccounts={()=>setModal('accounts')}/><div className="settings-about"><img src="/freedom.svg" alt="" /><div><strong>Freedom GPT <span>{appVersion.version}</span></strong><p>{t("Локальный ИИ · код и изображения")}</p></div></div><div className="settings-path"><span>{t("Данные интерфейса")}</span><code>{boot?.root}</code></div><p className="muted-copy">{t("Работает с установленной моделью без Ollama и платных API. Интернет нужен для сайтов, внешних сервисов и недостающих загрузок.")}</p><ProgramUpdate/></Modal>}
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
const cameraPhoneRoom=new URLSearchParams(location.search).get('camera_phone');
createRoot(document.getElementById('root')).render(cameraPhoneRoom?<React.Suspense fallback={<p className="panel-intro">Freedom Avatar…</p>}><CameraPhone room={cameraPhoneRoom}/></React.Suspense>:<App />);
