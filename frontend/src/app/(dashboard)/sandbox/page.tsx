'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  FileCode, 
  MonitorPlay, 
  Smartphone, 
  Play, 
  Code2,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Copy,
  CheckCircle2,
  ExternalLink,
  Laptop,
  Loader2,
  AlertCircle,
  Sparkles,
  Send,
  Wand2,
  Download,
  FolderOpen
} from 'lucide-react';
import { mvpApi } from '@/lib/api';
import { MVPBuild } from '@/types';

type ViewMode = 'code' | 'preview' | 'split';
type DeviceSize = 'desktop' | 'mobile';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  updated_files?: string[];
  timestamp: string;
}

const QUICK_SUGGESTIONS = [
  '🌟 Switch to Emerald Green color theme',
  '✨ Add Customer Reviews & Ratings section',
  '🏷️ Add 20% OFF Announcement Banner',
  '🔍 Add Search and Filter to catalog',
];

function SandboxContent() {
  const searchParams = useSearchParams();
  const buildId = searchParams.get('buildId');
  
  const [build, setBuild] = useState<MVPBuild | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // File state
  const [activeFile, setActiveFile] = useState<string>('');
  const [fileContents, setFileContents] = useState<Record<string, string>>({});
  const [fileLoading, setFileLoading] = useState(false);
  const [recentlyUpdatedFiles, setRecentlyUpdatedFiles] = useState<string[]>([]);
  
  // Layout state
  const [viewMode, setViewMode] = useState<ViewMode>('split');
  const [deviceSize, setDeviceSize] = useState<DeviceSize>('desktop');
  const [isCopied, setIsCopied] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [expandedFolders, setExpandedFolders] = useState<Record<string, boolean>>({
    'src': true,
    'root': true,
    'frontend/src/app': true,
    'frontend/src': true,
    'frontend': true,
  });

  // Chat Edit state
  const chatMsgCounterRef = useRef(0);
  const nextChatId = (prefix: string) => {
    chatMsgCounterRef.current += 1;
    return `${prefix}-${chatMsgCounterRef.current}`;
  };

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'I am your SUTRA AI Sandbox Editor. Describe any changes you want to make—such as updating branding, tweaking color palettes, adding new components, or adjusting schemas—and I will update the code and live preview instantly.',
      timestamp: 'Just now',
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [isApplyingEdit, setIsApplyingEdit] = useState(false);
  const [editStatusText, setEditStatusText] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isApplyingEdit]);

  // Handle responsive layout based on window size
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024 && viewMode === 'split') {
        setViewMode('preview');
      }
      if (window.innerWidth < 1280) {
        setIsChatOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();
    return () => window.removeEventListener('resize', handleResize);
  }, [viewMode]);

  // Fetch build details
  useEffect(() => {
    if (!buildId) return;
    
    let isMounted = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsLoading(true);
    
    mvpApi.getStatus(buildId)
      .then(data => {
        if (!isMounted) return;
        setBuild(data);
        
        // Find a default file to open (e.g. page.tsx or package.json)
        if (data.files && data.files.length > 0) {
          const files = data.files.filter(f => !f.is_dir).map(f => f.path);
          const defaultFile = files.find(f => f.includes('src/app/page.tsx')) || 
                              files.find(f => f.includes('src/App.tsx')) || 
                              files.find(f => f.includes('package.json')) || 
                              files[0];
          
          if (defaultFile) {
            setActiveFile(defaultFile);
          }
        }
      })
      .catch(err => {
        if (isMounted) setError(err.message || 'Failed to load sandbox data');
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });
      
    return () => { isMounted = false; };
  }, [buildId]);

  // Fetch file content when active file changes
  useEffect(() => {
    if (!buildId || !activeFile || fileContents[activeFile]) return;
    
    let isMounted = true;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFileLoading(true);
    
    mvpApi.getFileContent(buildId, activeFile)
      .then(content => {
        if (isMounted) {
          setFileContents(prev => ({ ...prev, [activeFile]: content }));
        }
      })
      .catch(err => {
        console.error("Failed to load file content", err);
        if (isMounted) {
          setFileContents(prev => ({ ...prev, [activeFile]: `// Failed to load content: ${err.message}` }));
        }
      })
      .finally(() => {
        if (isMounted) setFileLoading(false);
      });
      
    return () => { isMounted = false; };
  }, [buildId, activeFile, fileContents]);

  const handleCopyCode = () => {
    const content = fileContents[activeFile] || '';
    navigator.clipboard.writeText(content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => setIsRefreshing(false), 800);
  };

  const handleDownload = () => {
    if (!buildId) return;
    mvpApi.downloadBuild(buildId, `sandbox_build_${buildId.slice(0, 8)}.zip`).catch(console.error);
  };

  const toggleFolder = (folder: string) => {
    setExpandedFolders(prev => ({ ...prev, [folder]: !prev[folder] }));
  };

  // Extract folder and filename from path
  const getFileParts = (path: string) => {
    const parts = path.split('/');
    if (parts.length === 1) return { folder: 'root', name: parts[0] };
    const name = parts.pop() || '';
    return { folder: parts.join('/'), name };
  };

  const filePaths = build?.files?.filter(f => !f.is_dir).map(f => f.path) || [];
  
  const groupedFiles = filePaths.reduce((acc, path) => {
    const { folder } = getFileParts(path);
    if (!acc[folder]) acc[folder] = [];
    acc[folder].push(path);
    return acc;
  }, {} as Record<string, string[]>);

  // Chat Edit Handler
  const handleSendEdit = async (overridePrompt?: string) => {
    const text = (overridePrompt || chatInput).trim();
    if (!text || isApplyingEdit || !buildId) return;

    setChatInput('');
    const userMsg: ChatMessage = {
      id: nextChatId('user'),
      role: 'user',
      content: text,
      timestamp: 'Just now',
    };
    setChatMessages(prev => [...prev, userMsg]);
    setIsApplyingEdit(true);
    setEditStatusText('Analyzing workspace & synthesizing code...');

    try {
      const result = await mvpApi.chatEdit(buildId, text, activeFile);

      // Update file contents cache
      const updatedPaths: string[] = [];
      const newContents = { ...fileContents };
      if (result.updated_files && result.updated_files.length > 0) {
        result.updated_files.forEach(f => {
          newContents[f.path] = f.content;
          updatedPaths.push(f.path);
        });
        setFileContents(newContents);
        setRecentlyUpdatedFiles(updatedPaths);

        // Switch to the first updated file if activeFile is not in updated list
        if (!updatedPaths.includes(activeFile)) {
          setActiveFile(updatedPaths[0]);
        }
      }

      // Update build file tree
      if (result.all_files) {
        setBuild(prev => prev ? { ...prev, files: result.all_files, file_count: result.all_files.length } : prev);
      }

      // Append assistant response
      const assistantMsg: ChatMessage = {
        id: nextChatId('assistant'),
        role: 'assistant',
        content: result.message || 'Edits applied successfully to your codebase.',
        updated_files: updatedPaths,
        timestamp: 'Just now',
      };
      setChatMessages(prev => [...prev, assistantMsg]);

      // Trigger hot refresh on live preview
      handleRefresh();

      // Clear recently updated highlight after 6 seconds
      setTimeout(() => {
        setRecentlyUpdatedFiles([]);
      }, 6000);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Edit failed to apply';
      const errorMsg: ChatMessage = {
        id: nextChatId('err'),
        role: 'assistant',
        content: `Error applying edit: ${errMsg}. Please try again with a specific request.`,
        timestamp: 'Just now',
      };
      setChatMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsApplyingEdit(false);
      setEditStatusText('');
    }
  };

  // Preview URL: prefer deployed URL, else use backend live sandbox HTML preview endpoint
  const previewUrl = build?.frontend_url || build?.render_service_url || (buildId ? mvpApi.getPreviewUrl(buildId) : null);

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] -mx-2 lg:-mx-4 mt-[-10px] sutra-surface rounded-md overflow-hidden shadow-sm border border-[var(--border)]">
      {/* Sandbox Header */}
      <div className="h-14 border-b border-[var(--border)] bg-[var(--bg-2)] flex items-center justify-between px-4 shrink-0 z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-sm bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] flex items-center justify-center shadow-sm">
              <Code2 className="w-4 h-4 text-[var(--sutra-muted-gold)]" />
            </div>
            <div>
              <span className="font-semibold text-sm tracking-tight text-[var(--sutra-charcoal)]">SUTRA Live Sandbox</span>
              {Boolean(build?.app_config?.app_name) && (
                <span className="hidden sm:inline-block text-[11px] text-[var(--text-3)] font-mono ml-2">
                  — {String(build?.app_config?.app_name)}
                </span>
              )}
            </div>
          </div>

          <div className="h-4 w-px bg-[var(--border)] hidden md:block"></div>

          {/* AI Chat Toggle Button */}
          <button
            onClick={() => setIsChatOpen(prev => !prev)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-sm flex items-center gap-1.5 transition-all shadow-sm ${
              isChatOpen 
                ? 'bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] border border-[var(--sutra-charcoal)]' 
                : 'bg-[var(--bg)] text-[var(--sutra-charcoal)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)]'
            }`}
          >
            <Sparkles className={`w-3.5 h-3.5 ${isChatOpen ? 'text-[var(--sutra-muted-gold)] animate-pulse' : 'text-[var(--text-2)]'}`} />
            <span>AI Edit Chat</span>
          </button>

          {/* View Mode Segmented Control */}
          <div className="hidden md:flex items-center gap-1 bg-[var(--bg-3)] p-1 rounded-sm border border-[var(--border)]">
            <button 
              onClick={() => setViewMode('code')}
              className={`px-3 py-1 text-xs font-medium rounded-sm flex items-center gap-1.5 transition-all ${viewMode === 'code' ? 'bg-[var(--bg-2)] shadow-sm text-[var(--text)] border border-[var(--border)]' : 'text-[var(--text-2)] hover:text-[var(--text)] border border-transparent'}`}
            >
              <FileCode className="w-3.5 h-3.5" /> Code
            </button>
            <button 
              onClick={() => setViewMode('split')}
              className={`px-3 py-1 text-xs font-medium rounded-sm flex items-center gap-1.5 transition-all hidden lg:flex ${viewMode === 'split' ? 'bg-[var(--bg-2)] shadow-sm text-[var(--text)] border border-[var(--border)]' : 'text-[var(--text-2)] hover:text-[var(--text)] border border-transparent'}`}
            >
              <MonitorPlay className="w-3.5 h-3.5" /> Split
            </button>
            <button 
              onClick={() => setViewMode('preview')}
              className={`px-3 py-1 text-xs font-medium rounded-sm flex items-center gap-1.5 transition-all ${viewMode === 'preview' ? 'bg-[var(--bg-2)] shadow-sm text-[var(--text)] border border-[var(--border)]' : 'text-[var(--text-2)] hover:text-[var(--text)] border border-transparent'}`}
            >
              <Play className="w-3.5 h-3.5" /> Preview
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          {isApplyingEdit ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--amber)] bg-[#B08A4A1A] px-2.5 py-1 rounded-sm border border-[#B08A4A33] animate-pulse">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--sutra-muted-gold)]" />
              <span>Applying Edits...</span>
            </span>
          ) : build?.status === 'complete' ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--green)] bg-[#2F8A4B1A] px-2.5 py-1 rounded-sm border border-[#2F8A4B33]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--green)]"></span>
              Environment Ready
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--amber)] bg-[#B08A4A1A] px-2.5 py-1 rounded-sm border border-[#B08A4A33]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--amber)] animate-pulse"></span>
              Building...
            </span>
          )}

          {buildId && (
            <button
              onClick={handleDownload}
              className="btn btn-secondary h-8 px-3 text-xs flex items-center gap-1.5"
              title="Download project as ZIP"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">ZIP</span>
            </button>
          )}

          {build?.repo_url && (
            <a 
              href={build.repo_url} 
              target="_blank" 
              rel="noopener noreferrer" 
              className="btn btn-secondary h-8 px-3 text-xs flex items-center gap-1.5"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">GitHub</span>
            </a>
          )}
        </div>
      </div>

      {/* Main Sandbox Area */}
      <div className="flex-1 flex overflow-hidden bg-[var(--bg-3)] relative">
        
        {/* PANE 1: AI CHAT ASSISTANT (LOVABLE EDIT MODE) */}
        <AnimatePresence initial={false}>
          {isChatOpen && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 360, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="border-r border-[var(--border)] bg-[var(--bg)] h-full flex flex-col shrink-0 z-10 overflow-hidden shadow-sm"
            >
              {/* Chat Header */}
              <div className="h-10 px-4 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-2)] shrink-0">
                <div className="flex items-center gap-2">
                  <Wand2 className="w-3.5 h-3.5 text-[var(--sutra-muted-gold)]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-charcoal)]">
                    AI Architect Chat
                  </span>
                </div>
                <span className="text-[10px] font-mono text-[var(--text-3)]">Lovable Mode</span>
              </div>

              {/* Chat Messages List */}
              <div className="flex-1 p-3.5 overflow-y-auto space-y-3.5 bg-gradient-to-b from-[var(--bg)] to-[var(--bg-2)]">
                {chatMessages.map(msg => (
                  <div 
                    key={msg.id}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <div className="flex items-center gap-1.5 mb-1 px-1 text-[10px] text-[var(--text-3)] font-mono">
                      <span>{msg.role === 'user' ? 'You' : 'SUTRA AI'}</span>
                      <span>·</span>
                      <span>{msg.timestamp}</span>
                    </div>

                    <div 
                      className={`p-3 rounded-sm text-xs leading-relaxed max-w-[92%] shadow-sm ${
                        msg.role === 'user'
                          ? 'bg-[var(--sutra-charcoal)] text-[var(--sutra-warm-ivory)] border border-[var(--sutra-charcoal)]'
                          : 'bg-[var(--bg)] text-[var(--text)] border border-[var(--border)]'
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>

                      {/* Chips of updated files */}
                      {msg.updated_files && msg.updated_files.length > 0 && (
                        <div className="mt-2.5 pt-2 border-t border-[var(--border)]">
                          <span className="text-[10px] font-semibold text-[var(--text-2)] uppercase tracking-wider block mb-1.5">
                            Modified Files:
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {msg.updated_files.map(filePath => (
                              <button
                                key={filePath}
                                onClick={() => setActiveFile(filePath)}
                                className={`text-[11px] font-mono px-2 py-0.5 rounded-sm border flex items-center gap-1 transition-all ${
                                  activeFile === filePath
                                    ? 'bg-[var(--sutra-muted-gold)] text-white border-[var(--sutra-muted-gold)]'
                                    : 'bg-[var(--bg-2)] text-[var(--sutra-charcoal)] border-[var(--border)] hover:border-[var(--sutra-muted-gold)]'
                                }`}
                              >
                                <CheckCircle2 className="w-3 h-3 text-[var(--green)]" />
                                <span className="truncate max-w-[140px]">{getFileParts(filePath).name}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isApplyingEdit && (
                  <div className="flex flex-col items-start animate-fade-in">
                    <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-muted-gold)] rounded-sm text-xs text-[var(--text-2)] shadow-sm flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--sutra-muted-gold)] shrink-0" />
                      <span className="font-mono text-[11px]">{editStatusText || 'Applying modifications to codebase...'}</span>
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Quick Prompts Suggestions */}
              <div className="px-3 py-2 bg-[var(--bg-2)] border-t border-[var(--border)]">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-3)] mb-1.5">
                  Suggested Edits:
                </div>
                <div className="flex flex-wrap gap-1">
                  {QUICK_SUGGESTIONS.map(prompt => (
                    <button
                      key={prompt}
                      onClick={() => handleSendEdit(prompt)}
                      disabled={isApplyingEdit}
                      className="text-[10px] px-2 py-1 bg-[var(--bg)] hover:bg-[var(--bg-3)] border border-[var(--border)] hover:border-[var(--sutra-muted-gold)] rounded-sm text-[var(--text-2)] hover:text-[var(--text)] transition-colors truncate max-w-full disabled:opacity-50"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Chat Input */}
              <div className="p-3 border-t border-[var(--border)] bg-[var(--bg)]">
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSendEdit();
                  }}
                  className="flex gap-2"
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Describe edits to UI or code..."
                    disabled={isApplyingEdit}
                    className="flex-1 py-2 px-3 bg-[var(--bg-2)] border border-[var(--border)] text-xs text-[var(--sutra-charcoal)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] rounded-sm transition-colors shadow-inner"
                  />
                  <button
                    type="submit"
                    disabled={!chatInput.trim() || isApplyingEdit}
                    className="p-2 rounded-sm bg-[var(--sutra-charcoal)] hover:bg-black text-white disabled:opacity-40 transition-colors shadow-sm shrink-0"
                    title="Send edit request"
                  >
                    {isApplyingEdit ? (
                      <Loader2 className="w-4 h-4 animate-spin text-[var(--sutra-muted-gold)]" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </button>
                </form>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* PANE 2: CODE EXPLORER & EDITOR */}
        <AnimatePresence initial={false}>
          {(viewMode === 'code' || viewMode === 'split') && (
            <motion.div 
              initial={{ width: 0, opacity: 0 }}
              animate={{ 
                width: viewMode === 'split' ? (isChatOpen ? 'calc(50% - 180px)' : '50%') : (isChatOpen ? 'calc(100% - 360px)' : '100%'), 
                opacity: 1 
              }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="flex border-r border-[var(--border)] bg-[#1e1e1e] h-full relative z-10 shrink-0 overflow-hidden"
            >
              {isLoading && !build ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3">
                   <Loader2 className="w-8 h-8 text-[var(--sutra-muted-gold)] animate-spin" />
                   <p className="text-xs text-[#888] font-mono">Loading project workspace...</p>
                </div>
              ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center text-[#ff6b6b] p-8 text-center">
                   <AlertCircle className="w-12 h-12 mb-4 opacity-80" />
                   <p className="font-medium text-sm">{error}</p>
                   <p className="text-xs opacity-70 mt-2">Make sure you have passed a valid buildId in the URL</p>
                </div>
              ) : !buildId ? (
                <div className="flex-1 flex flex-col items-center justify-center text-[#888] p-8 text-center space-y-4">
                   <FolderOpen className="w-12 h-12 mb-2 text-[var(--sutra-muted-gold)] opacity-70" />
                   <h3 className="font-semibold text-white text-sm">No Build Selected</h3>
                   <p className="text-xs text-[#aaa] max-w-sm">
                     To enter the Live Sandbox, pass <span className="font-mono text-[#B08A4A]">?buildId=...</span> in the URL, or build an application using the AI Architect.
                   </p>
                   <Link href="/chat" className="btn btn-primary text-xs px-4 py-2 mt-2">
                     Go to AI Architect Chat →
                   </Link>
                </div>
              ) : (
                <>
                  {/* File Explorer Sidebar */}
                  <div className="w-52 shrink-0 border-r border-[#333] bg-[#181818] flex flex-col">
                    <div className="h-10 px-3.5 flex items-center justify-between text-xs font-semibold text-[#888] uppercase tracking-wider border-b border-[#333]">
                      <span>Explorer</span>
                      <span className="text-[10px] font-mono text-[#555]">{filePaths.length} files</span>
                    </div>
                    <div className="p-2 overflow-y-auto flex-1">
                      {Object.keys(groupedFiles).length === 0 && (
                        <div className="text-xs text-[#555] p-2 italic">No files found in build.</div>
                      )}
                      
                      {Object.entries(groupedFiles).map(([folder, files]) => (
                        <div key={folder} className="mb-1">
                          {folder !== 'root' && (
                            <button 
                              onClick={() => toggleFolder(folder)}
                              className="flex items-center gap-1 w-full text-left px-2 py-1 text-sm text-[#ccc] hover:bg-[#2a2a2a] rounded-sm transition-colors overflow-hidden"
                            >
                              {expandedFolders[folder] ? <ChevronDown className="w-3.5 h-3.5 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 shrink-0" />}
                              <span className="font-medium text-xs truncate">{folder}</span>
                            </button>
                          )}
                          
                          <AnimatePresence>
                            {(expandedFolders[folder] || folder === 'root') && (
                              <motion.div 
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className={`${folder !== 'root' ? 'pl-3' : ''}`}
                              >
                                {files.map(path => {
                                  const { name } = getFileParts(path);
                                  const isActive = activeFile === path;
                                  const isRecentlyUpdated = recentlyUpdatedFiles.includes(path);

                                  return (
                                    <button
                                      key={path}
                                      onClick={() => setActiveFile(path)}
                                      className={`flex items-center justify-between gap-1.5 w-full text-left px-2 py-1 text-xs rounded-sm transition-colors my-0.5 ${
                                        isActive 
                                          ? 'bg-[#37373d] text-white font-medium' 
                                          : isRecentlyUpdated
                                          ? 'text-[#569cd6] bg-[#264f7833] hover:bg-[#264f7855]'
                                          : 'text-[#999] hover:bg-[#2a2a2a] hover:text-[#ccc]'
                                      }`}
                                    >
                                      <div className="flex items-center gap-1.5 truncate">
                                        {name.endsWith('.tsx') || name.endsWith('.ts') ? (
                                          <span className="text-[#519aba] shrink-0 font-bold">{"</>"}</span>
                                        ) : name.endsWith('.css') ? (
                                          <span className="text-[#c4722a] shrink-0 font-bold">#</span>
                                        ) : name.endsWith('.json') ? (
                                          <span className="text-[#cbcb41] shrink-0 font-bold">{"{}"}</span>
                                        ) : (
                                          <FileCode className="w-3 h-3 text-[#888] shrink-0" />
                                        )}
                                        <span className="truncate">{name}</span>
                                      </div>

                                      {isRecentlyUpdated && (
                                        <span className="w-1.5 h-1.5 rounded-full bg-[#569cd6] shrink-0 animate-ping" />
                                      )}
                                    </button>
                                  );
                                })}
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Code Editor View */}
                  <div className="flex-1 flex flex-col min-w-0">
                    {/* Editor Tabs */}
                    <div className="flex bg-[#1e1e1e] overflow-x-auto no-scrollbar shrink-0 relative border-b border-[#333]">
                      <div className="flex">
                        {activeFile ? (
                          <div className="px-3.5 py-2 bg-[#1e1e1e] border-t-2 border-[#B08A4A] border-r border-[#333] text-white text-xs font-medium flex items-center gap-2 -mb-px">
                            <span>{getFileParts(activeFile).name}</span>
                            {recentlyUpdatedFiles.includes(activeFile) && (
                              <span className="text-[9px] uppercase tracking-wider font-bold text-[#569cd6] bg-[#264f78] px-1.5 py-0.2 rounded-sm">
                                Updated
                              </span>
                            )}
                          </div>
                        ) : (
                          <div className="px-4 py-2 text-[#555] text-xs font-medium">
                            Select a file to view
                          </div>
                        )}
                      </div>
                      
                      {/* Editor Actions */}
                      {activeFile && (
                        <div className="ml-auto pr-3 flex items-center gap-2 z-20">
                          <button 
                            onClick={handleCopyCode}
                            className="p-1.5 text-[#888] hover:text-white bg-[#2a2a2a] hover:bg-[#333] rounded-sm transition-colors border border-[#444] shadow-sm flex items-center gap-1.5 text-xs font-mono"
                            title="Copy code"
                          >
                            {isCopied ? <CheckCircle2 className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                            <span className="hidden sm:inline">{isCopied ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Editor Content Area */}
                    <div className="flex-1 overflow-auto bg-[#1e1e1e] p-4 text-sm font-mono leading-relaxed relative">
                      {fileLoading ? (
                        <div className="absolute inset-0 flex items-center justify-center bg-[#1e1e1e]/80">
                           <Loader2 className="w-6 h-6 text-[#888] animate-spin" />
                        </div>
                      ) : activeFile && fileContents[activeFile] ? (
                        <>
                          {/* Line numbers */}
                          <div className="absolute left-0 top-4 bottom-4 w-11 border-r border-[#333] text-right pr-3 text-[#555] select-none text-xs font-mono overflow-hidden">
                            {fileContents[activeFile].split('\n').map((_, i) => (
                              <div key={i}>{i + 1}</div>
                            ))}
                          </div>
                          <div className="pl-10">
                            <pre className="text-[#d4d4d4] margin-0 font-mono text-[13px] tab-size-2">
                              <code dangerouslySetInnerHTML={{ 
                                __html: fileContents[activeFile]
                                  .replace(/</g, '&lt;')
                                  .replace(/>/g, '&gt;')
                                  .replace(/\b(import|from|export|default|const|let|var|return|function|class|await|async|interface|type)\b/g, match => `<span class="text-[#569cd6] font-semibold">${match}</span>`)
                                  .replace(/\b(useState|useEffect|useCallback|useRef|useMemo)\b/g, match => `<span class="text-[#4ec9b0]">${match}</span>`)
                                  .replace(/\b(className|onClick|onChange|onSubmit|key|href|src|type|value|disabled)\b=/g, match => `<span class="text-[#9cdcfe]">${match}</span>`)
                                  .replace(/(".*?"|'.*?'|`.*?`)/g, match => `<span class="text-[#ce9178]">${match}</span>`)
                                  .replace(/&lt;([A-Z][a-zA-Z0-9]*)/g, '&lt;<span class="text-[#4ec9b0] font-medium">$1</span>')
                                  .replace(/&lt;([a-z][a-zA-Z0-9]*)/g, '&lt;<span class="text-[#569cd6]">$1</span>')
                                  .replace(/([A-Z][a-zA-Z0-9]*)\s*\(/g, '<span class="text-[#dcdcaa]">$1</span>(')
                              }} />
                            </pre>
                          </div>
                        </>
                      ) : (
                        <div className="text-[#666] text-center mt-20 italic text-xs">
                           {activeFile ? "Empty file" : "Select a file from the explorer to view its contents"}
                        </div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* PANE 3: LIVE BROWSER PREVIEW */}
        <AnimatePresence initial={false}>
          {(viewMode === 'preview' || viewMode === 'split') && (
            <motion.div 
              initial={{ width: 0, opacity: 0 }}
              animate={{ 
                width: viewMode === 'split' ? (isChatOpen ? 'calc(50% + 180px)' : '50%') : (isChatOpen ? 'calc(100% - 360px)' : '100%'), 
                opacity: 1 
              }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="h-full flex flex-col bg-[var(--bg-3)] shrink-0 overflow-hidden"
            >
              {/* Browser Header Bar */}
              <div className="h-12 border-b border-[var(--border)] bg-[var(--bg-2)] flex items-center justify-between px-4 shrink-0 shadow-sm relative z-10">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5 mr-2">
                    <div className="w-3 h-3 rounded-full bg-[#ED6A5E] border border-[#D24F44]"></div>
                    <div className="w-3 h-3 rounded-full bg-[#F5BF4F] border border-[#D4A33B]"></div>
                    <div className="w-3 h-3 rounded-full bg-[#61C554] border border-[#50A444]"></div>
                  </div>
                  
                  {/* Address Bar */}
                  <div className="flex items-center gap-2 bg-[var(--bg-3)] border border-[var(--border)] rounded-sm px-3 py-1.5 min-w-[200px] max-w-sm flex-1 shadow-inner">
                    <div className="text-[var(--text-3)]">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                    </div>
                    <span className="text-xs text-[var(--text-2)] font-mono truncate">
                      {previewUrl ? 'live-preview:3000' : 'localhost:3000'}
                    </span>
                    <button 
                      onClick={handleRefresh} 
                      className="ml-auto text-[var(--text-3)] hover:text-[var(--text)] transition-colors"
                      title="Reload preview"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[var(--sutra-muted-gold)]' : ''}`} />
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Device toggle */}
                  <div className="flex items-center bg-[var(--bg-3)] p-1 rounded-sm border border-[var(--border)]">
                    <button 
                      onClick={() => setDeviceSize('desktop')}
                      className={`p-1.5 rounded-sm transition-colors ${deviceSize === 'desktop' ? 'bg-[var(--bg-2)] shadow-sm text-[var(--text)]' : 'text-[var(--text-3)] hover:text-[var(--text)]'}`}
                      title="Desktop view"
                    >
                      <Laptop className="w-3.5 h-3.5" />
                    </button>
                    <button 
                      onClick={() => setDeviceSize('mobile')}
                      className={`p-1.5 rounded-sm transition-colors ${deviceSize === 'mobile' ? 'bg-[var(--bg-2)] shadow-sm text-[var(--text)]' : 'text-[var(--text-3)] hover:text-[var(--text)]'}`}
                      title="Mobile phone view"
                    >
                      <Smartphone className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {previewUrl && (
                    <>
                      <div className="h-4 w-px bg-[var(--border)] mx-1"></div>
                      <a 
                        href={previewUrl} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="text-[var(--text-2)] hover:text-[var(--text)] transition-colors p-1" 
                        title="Open preview in new tab"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </>
                  )}
                </div>
              </div>

              {/* Browser Canvas */}
              <div className="flex-1 overflow-auto flex items-center justify-center p-4 lg:p-6 bg-gradient-to-br from-[var(--bg-3)] to-[var(--bg)] bg-sutra-grid">
                <div 
                  className={`bg-white shadow-xl rounded-sm overflow-hidden border border-[var(--border)] transition-all duration-300 ease-in-out relative ${
                    isRefreshing ? 'opacity-60 scale-[0.99]' : 'opacity-100 scale-100'
                  }`}
                  style={{
                    width: deviceSize === 'mobile' ? '375px' : '100%',
                    height: deviceSize === 'mobile' ? '667px' : '100%',
                    maxWidth: deviceSize === 'desktop' ? '1200px' : '375px',
                    maxHeight: deviceSize === 'desktop' ? '820px' : '667px',
                  }}
                >
                  {isRefreshing && (
                    <div className="absolute inset-0 z-50 flex items-center justify-center bg-white/60 backdrop-blur-xs">
                      <div className="flex items-center gap-2 p-3 bg-white shadow-lg rounded-sm border border-[var(--border)]">
                        <Loader2 className="w-5 h-5 text-[var(--sutra-muted-gold)] animate-spin" />
                        <span className="text-xs font-mono text-[var(--sutra-charcoal)] font-medium">Refreshing Live Preview...</span>
                      </div>
                    </div>
                  )}
                  
                  {previewUrl ? (
                    <iframe 
                      key={isRefreshing ? 'refreshing' : 'active'}
                      src={previewUrl} 
                      className="w-full h-full border-none"
                      title="Live Interactive Preview"
                      sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                    />
                  ) : (
                    <div className="w-full h-full bg-[#FAF8F3] flex flex-col items-center justify-center p-6 font-sans text-center">
                      <MonitorPlay className="w-16 h-16 text-[#E5DED1] mb-4" />
                      <h2 className="text-lg font-bold text-[#171A1C] mb-1">Preview Awaiting Build</h2>
                      <p className="text-[#77736B] max-w-sm text-xs leading-relaxed">
                        {buildId 
                          ? "Loading live interactive environment for this build..." 
                          : "Select or trigger a build to view the live sandbox."}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

export default function SandboxPage() {
  return (
    <Suspense fallback={
      <div className="flex h-[calc(100vh-140px)] items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--sutra-muted-gold)]" />
        <span className="text-sm font-mono text-[var(--text-2)]">Initializing Live Sandbox...</span>
      </div>
    }>
      <SandboxContent />
    </Suspense>
  );
}
