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
import { VoiceInputButton } from '@/components/VoiceInputButton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/cn';
import { CodeViewer } from '@/components/CodeViewer';
import { TreeView, type TreeNode } from '@/components/lab/tree-view';

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

function createFileTree(files: { path: string; is_dir?: boolean }[]): TreeNode[] {
  const roots: TreeNode[] = [];
  const index = new Map<string, TreeNode>();

  for (const file of files) {
    const parts = file.path.split('/').filter(Boolean);
    if (parts.length === 0) continue;

    let siblings = roots;
    let parentPath = '';

    parts.forEach((part, position) => {
      const path = parentPath ? `${parentPath}/${part}` : part;
      const isDirectory = position < parts.length - 1 || Boolean(file.is_dir);
      let node = index.get(path);

      if (!node) {
        node = {
          name: part,
          kind: isDirectory ? 'folder' : 'file',
          path: isDirectory ? undefined : path,
          ...(isDirectory ? { children: [] } : {}),
        };
        index.set(path, node);
        siblings.push(node);
      } else if (isDirectory) {
        node.kind = 'folder';
        node.path = undefined;
        node.children ??= [];
      }

      if (isDirectory) siblings = node.children ?? (node.children = []);
      parentPath = path;
    });
  }

  const sort = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      const aFolder = a.kind === 'folder' ? 0 : 1;
      const bFolder = b.kind === 'folder' ? 0 : 1;
      return aFolder - bFolder || a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
    });
    nodes.forEach((node) => node.children && sort(node.children));
  };
  sort(roots);
  return roots;
}

function SandboxContent() {
  const searchParams = useSearchParams();
  const buildId = searchParams.get('buildId');
  
  const [build, setBuild] = useState<MVPBuild | null>(null);
  const [isLoading, setIsLoading] = useState(true);
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
  const [refreshKey, setRefreshKey] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(true);

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
  const refreshTimerRef = useRef<number | null>(null);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, isApplyingEdit]);

  useEffect(() => () => {
    if (refreshTimerRef.current !== null) window.clearTimeout(refreshTimerRef.current);
  }, []);

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

  const handleCopyCode = async () => {
    const content = fileContents[activeFile] || '';
    try {
      await navigator.clipboard.writeText(content);
      setIsCopied(true);
      window.setTimeout(() => setIsCopied(false), 1800);
    } catch {
      setError('Clipboard access is unavailable in this browser.');
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    setRefreshKey((key) => key + 1);
    if (refreshTimerRef.current !== null) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = window.setTimeout(() => setIsRefreshing(false), 500);
  };

  const handleDownload = () => {
    if (!buildId) return;
    mvpApi.downloadBuild(buildId, `sandbox_build_${buildId.slice(0, 8)}.zip`).catch((err) => {
      setError(err instanceof Error ? err.message : 'Could not download this build.');
    });
  };

  // Extract the filename from a path for the editor tab and changed-file chips.
  const getFileParts = (path: string) => {
    const parts = path.split('/');
    const name = parts.pop() || '';
    return { folder: parts.join('/'), name };
  };

  const filePaths = build?.files?.filter(f => !f.is_dir).map(f => f.path) || [];
  const fileTree = React.useMemo(() => createFileTree(build?.files ?? []), [build?.files]);

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
    <div className="-mx-2 -mt-3 flex h-[calc(100dvh-5rem)] min-h-[32rem] flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--background)] shadow-sm sm:-mx-3 lg:-mx-4">
      {/* Sandbox Header */}
      <div className="z-20 flex min-h-14 shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2 sm:px-4">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[var(--foreground)] text-[var(--background)] shadow-sm">
              <Code2 className="size-4" />
            </div>
            <div>
              <span className="font-semibold text-sm tracking-tight text-[var(--sutra-ink)]">SUTRA Live Sandbox</span>
              {Boolean(build?.app_config?.app_name) && (
                <span className="ml-2 hidden max-w-56 truncate align-bottom font-mono text-[11px] text-[var(--text-3)] sm:inline-block">
                  — {String(build?.app_config?.app_name)}
                </span>
              )}
            </div>
          </div>

          <div className="h-4 w-px bg-[var(--border)] hidden md:block"></div>

          {/* AI Chat Toggle Button */}
          <Button
            type="button"
            onClick={() => setIsChatOpen(prev => !prev)}
            variant={isChatOpen ? 'secondary' : 'outline'}
            size="sm"
            aria-expanded={isChatOpen}
          >
            <Sparkles className="size-3.5" />
            <span>AI Edit Chat</span>
          </Button>

          {/* View Mode Segmented Control */}
          <div className="flex items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 md:hidden" role="group" aria-label="Sandbox view">
            <Button type="button" variant={viewMode === 'preview' ? 'secondary' : 'ghost'} size="icon-sm" onClick={() => setViewMode('preview')} aria-label="Show preview" aria-pressed={viewMode === 'preview'}><Play /></Button>
            <Button type="button" variant={viewMode === 'code' ? 'secondary' : 'ghost'} size="icon-sm" onClick={() => setViewMode('code')} aria-label="Show code" aria-pressed={viewMode === 'code'}><FileCode /></Button>
          </div>
          <div className="hidden items-center gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1 md:flex" role="group" aria-label="Sandbox view">
            <Button
              type="button"
              variant={viewMode === 'code' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('code')}
              aria-pressed={viewMode === 'code'}
            >
              <FileCode /> Code
            </Button>
            <Button
              type="button"
              variant={viewMode === 'split' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('split')}
              className="hidden lg:inline-flex"
              aria-pressed={viewMode === 'split'}
            >
              <MonitorPlay /> Split
            </Button>
            <Button
              type="button"
              variant={viewMode === 'preview' ? 'secondary' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('preview')}
              aria-pressed={viewMode === 'preview'}
            >
              <Play /> Preview
            </Button>
          </div>
        </div>

        <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-2.5">
          {isApplyingEdit ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--amber)]">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Applying edits</span>
            </span>
          ) : build?.status === 'complete' ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--green)] bg-[#2F8A4B1A] px-2.5 py-1 rounded-sm border border-[#2F8A4B33]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--green)]"></span>
              Environment Ready
            </span>
          ) : build?.status === 'failed' ? (
            <span className="flex items-center gap-1.5 text-xs font-medium text-[var(--red)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--red)]"></span>
              Build failed
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
              className=""
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
              className=""
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">GitHub</span>
            </a>
          )}
        </div>
      </div>

      {/* Main Sandbox Area */}
      <div className={cn(
        'relative grid min-h-0 flex-1 overflow-hidden bg-[var(--bg-3)] grid-cols-1',
        isChatOpen && 'xl:grid-cols-[minmax(15rem,20rem)_minmax(0,1fr)]',
        viewMode === 'split' && (isChatOpen
          ? 'lg:grid-cols-2 xl:grid-cols-[minmax(15rem,20rem)_minmax(0,1fr)_minmax(0,1fr)]'
          : 'lg:grid-cols-2'),
      )}>
        
        {/* PANE 1: AI CHAT ASSISTANT (LOVABLE EDIT MODE) */}
        <AnimatePresence initial={false}>
          {isChatOpen && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="absolute inset-y-0 left-0 z-30 flex w-[min(22rem,calc(100vw-2rem))] min-h-0 min-w-0 flex-col overflow-hidden rounded-r-xl border-r border-[var(--border)] bg-[var(--background)] shadow-xl xl:static xl:z-auto xl:w-auto xl:rounded-none xl:shadow-sm"
            >
              {/* Chat Header */}
              <div className="h-10 px-4 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg-2)] shrink-0">
                <div className="flex items-center gap-2">
                  <Wand2 className="w-3.5 h-3.5 text-[var(--sutra-strong)]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--sutra-ink)]">
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
                          ? 'bg-[var(--sutra-ink)] text-[var(--sutra-warm-ivory)] border border-[var(--sutra-ink)]'
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
                              <Button
                                type="button"
                                variant="ghost"
                                size="xs"
                                key={filePath}
                                onClick={() => setActiveFile(filePath)}
                                className={cn('max-w-full font-mono',
                                  activeFile === filePath
                                    ? 'bg-[var(--accent)] text-[var(--foreground)]'
                                    : 'text-[var(--muted)]'
                                )}
                              >
                                <CheckCircle2 />
                                <span className="truncate max-w-[140px]">{getFileParts(filePath).name}</span>
                              </Button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                {isApplyingEdit && (
                  <div className="flex flex-col items-start animate-fade-in">
                    <div className="p-3 bg-[var(--bg)] border border-[var(--sutra-strong)] rounded-sm text-xs text-[var(--text-2)] shadow-sm flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--sutra-strong)] shrink-0" />
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
                    <Button
                      type="button"
                      variant="outline"
                      size="xs"
                      key={prompt}
                      onClick={() => handleSendEdit(prompt)}
                      disabled={isApplyingEdit}
                      className="h-auto max-w-full whitespace-normal text-left leading-snug"
                    >
                      {prompt}
                    </Button>
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
                  className="flex items-center gap-2"
                >
                  <Input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Describe edits to UI or code..."
                    disabled={isApplyingEdit}
                    className="min-w-0 flex-1"
                  />
                  <VoiceInputButton
                    onTranscribed={(text) => {
                      setChatInput((prev) => (prev ? `${prev} ${text}` : text));
                    }}
                    disabled={isApplyingEdit}
                  />
                  <Button
                    type="submit"
                    disabled={!chatInput.trim() || isApplyingEdit}
                    size="icon"
                    title="Send edit request"
                    aria-label="Send edit request"
                  >
                    {isApplyingEdit ? (
                      <Loader2 className="w-4 h-4 animate-spin text-[var(--sutra-strong)]" />
                    ) : (
                      <Send className="w-4 h-4" />
                    )}
                  </Button>
                </form>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* PANE 2: CODE EXPLORER & EDITOR */}
        <AnimatePresence initial={false}>
          {(viewMode === 'code' || viewMode === 'split') && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className="col-start-1 row-start-1 flex min-h-0 min-w-0 overflow-hidden border-b border-[var(--border)] bg-[#1e1e1e] lg:col-auto lg:row-auto lg:border-b-0 lg:border-r"
            >
              {isLoading && !build ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-3">
                   <Loader2 className="w-8 h-8 text-[var(--sutra-strong)] animate-spin" />
                   <p className="text-xs text-[#888] font-mono">Loading project workspace...</p>
                </div>
              ) : !buildId ? (
                <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center text-[var(--foreground)]">
                  <FolderOpen className="size-10 text-[var(--muted)]" />
                  <div className="space-y-1.5">
                    <h2 className="font-semibold">Choose a build to preview</h2>
                    <p className="max-w-sm text-sm text-[var(--muted)]">Open Live Sandbox from a completed build to inspect files and edit its preview.</p>
                  </div>
                  <Button asChild size="sm"><Link href="/chat"><Sparkles />Open AI Architect</Link></Button>
                </div>
              ) : error ? (
                <div className="flex-1 flex flex-col items-center justify-center text-[#ff6b6b] p-8 text-center">
                   <AlertCircle className="w-12 h-12 mb-4 opacity-80" />
                   <p className="font-medium text-sm">{error}</p>
                   <p className="text-xs opacity-70 mt-2">Make sure you have passed a valid buildId in the URL</p>
                </div>
              ) : (
                <>
                  {/* File Explorer Sidebar */}
                  <div className="flex w-56 shrink-0 flex-col border-r border-[#333] bg-[#181818]">
                    <div className="flex h-10 shrink-0 items-center justify-between border-b border-[#333] px-3.5 text-xs font-semibold uppercase tracking-wider text-[#888]">
                      <span>Files</span>
                      <span className="font-mono text-[10px] text-[#777]">{filePaths.length}</span>
                    </div>
                    <div className="min-h-0 flex-1 overflow-auto p-2">
                      {fileTree.length === 0 ? (
                        <p className="p-2 text-xs text-[#888]">No files found in this build.</p>
                      ) : (
                        <TreeView
                          key={filePaths.join('\n')}
                          nodes={fileTree}
                          label="Build files"
                          defaultOpenAll
                          selectedPath={activeFile || undefined}
                          markedPaths={recentlyUpdatedFiles}
                          onSelect={setActiveFile}
                          rowClassName="text-[12px] text-[#bbb] hover:text-white hover:bg-white/5"
                          className="gap-0.5"
                        />
                      )}
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
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={handleCopyCode}
                            title="Copy code"
                          >
                            {isCopied ? <CheckCircle2 /> : <Copy />}
                            {isCopied ? 'Copied' : 'Copy'}
                          </Button>
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
                          <CodeViewer
                            path={activeFile}
                            code={fileContents[activeFile]}
                            className="min-h-full min-w-max"
                          />
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
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25, ease: 'easeInOut' }}
              className={cn(
                'col-start-1 row-start-1 flex min-h-0 min-w-0 flex-col overflow-hidden bg-[var(--bg-3)] lg:col-auto lg:row-auto',
                viewMode === 'split' && (isChatOpen ? 'lg:col-start-2 xl:col-start-3' : 'lg:col-start-2'),
                viewMode !== 'split' && isChatOpen && 'xl:col-start-2',
              )}
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
                  <div className="flex min-w-0 max-w-sm flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 shadow-inner">
                    <div className="text-[var(--text-3)]">
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
                    </div>
                    <span className="text-xs text-[var(--text-2)] font-mono truncate">
                      {previewUrl ? 'live-preview:3000' : 'localhost:3000'}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={handleRefresh} 
                      title="Reload preview"
                      aria-label="Reload preview"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[var(--sutra-strong)]' : ''}`} />
                    </Button>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {/* Device toggle */}
                  <div className="flex items-center rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1" role="group" aria-label="Preview device size">
                    <Button
                      type="button"
                      variant={deviceSize === 'desktop' ? 'secondary' : 'ghost'}
                      size="icon-sm"
                      onClick={() => setDeviceSize('desktop')}
                      title="Desktop view"
                      aria-label="Desktop preview"
                      aria-pressed={deviceSize === 'desktop'}
                    >
                      <Laptop />
                    </Button>
                    <Button
                      type="button"
                      variant={deviceSize === 'mobile' ? 'secondary' : 'ghost'}
                      size="icon-sm"
                      onClick={() => setDeviceSize('mobile')}
                      title="Mobile phone view"
                      aria-label="Mobile preview"
                      aria-pressed={deviceSize === 'mobile'}
                    >
                      <Smartphone />
                    </Button>
                  </div>

                  {previewUrl && (
                    <>
                      <div className="h-4 w-px bg-[var(--border)] mx-1"></div>
                      <Button asChild variant="ghost" size="icon-sm">
                      <a
                        href={previewUrl} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        title="Open preview in new tab"
                        aria-label="Open preview in new tab"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                      </Button>
                    </>
                  )}
                </div>
              </div>

              {/* Browser Canvas */}
              <div className="flex-1 overflow-auto flex items-center justify-center p-2 lg:p-3 bg-gradient-to-br from-[var(--bg-3)] to-[var(--bg)] bg-sutra-grid">
                <div 
                  className={`bg-white shadow-xl rounded-sm overflow-hidden border border-[var(--border)] transition-all duration-300 ease-in-out relative ${
                    isRefreshing ? 'opacity-60 scale-[0.99]' : 'opacity-100 scale-100'
                  }`}
                  style={{
                    width: deviceSize === 'mobile' ? '375px' : '100%',
                    height: deviceSize === 'mobile' ? '667px' : '100%',
                    maxWidth: deviceSize === 'desktop' ? '100%' : '375px',
                    maxHeight: deviceSize === 'desktop' ? '100%' : '667px',
                  }}
                >
                  {isRefreshing && (
                    <div className="absolute inset-0 z-50 flex items-center justify-center bg-white/60 backdrop-blur-xs">
                      <div className="flex items-center gap-2 p-3 bg-white shadow-lg rounded-sm border border-[var(--border)]">
                        <Loader2 className="w-5 h-5 text-[var(--sutra-strong)] animate-spin" />
                        <span className="text-xs font-mono text-[var(--sutra-ink)] font-medium">Refreshing Live Preview...</span>
                      </div>
                    </div>
                  )}
                  
                  {previewUrl ? (
                    <iframe 
                      key={refreshKey}
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
      <div className="flex h-[calc(100vh-4.25rem)] items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--sutra-strong)]" />
        <span className="text-sm font-mono text-[var(--text-2)]">Initializing Live Sandbox...</span>
      </div>
    }>
      <SandboxContent />
    </Suspense>
  );
}
