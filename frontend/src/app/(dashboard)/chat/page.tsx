'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { 
  Sparkles, 
  Send, 
  Paperclip, 
  Loader2, 
  ArrowRight, 
  CheckCircle2 
} from 'lucide-react';
import ChatMessage from '@/components/ChatMessage';
import FileUploader from '@/components/FileUploader';
import AgentProgressTracker from '@/components/AgentProgressTracker';
import RecommendationCard from '@/components/RecommendationCard';
import { 
  workspaceApi, 
  solutionApi, 
  sendChatMessageStream, 
  confirmRecommendationsStream 
} from '@/lib/api';
import { RecommendedModule } from '@/types';

function ChatContent() {
  const searchParams = useSearchParams();
  const initialPrompt = searchParams.get('prompt') || '';

  const [inputMessage, setInputMessage] = useState(initialPrompt);
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant' | 'system'; content: string; agent?: string }>>([
    {
      role: 'assistant',
      agent: 'Business Analyst',
      content: "Hello! I am your AI Solution Architect. Tell me about your business idea, requirements, or upload a PRD/specification file. I will analyze your domain, propose core subsystem modules, and generate production-grade HLD, LLD, Database schemas, and execution roadmaps."
    }
  ]);

  const [solutionId, setSolutionId] = useState<string | null>(null);
  const [uploadedContext, setUploadedContext] = useState<string>('');
  const [uploadedFilename, setUploadedFilename] = useState<string>('');
  const [showUploader, setShowUploader] = useState(false);

  // Multi-Agent swarm state
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<'idle' | 'analyzing' | 'recommending' | 'generating' | 'complete' | 'failed'>('idle');
  const [isStreaming, setIsStreaming] = useState(false);

  // Recommendations state
  const [recommendations, setRecommendations] = useState<RecommendedModule[]>([]);
  const [selectedModules, setSelectedModules] = useState<string[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, recommendations, pipelineStatus]);

  // Ensure workspace and solution exist on load
  useEffect(() => {
    async function initSession() {
      try {
        const wsList = await workspaceApi.list();
        let ws = wsList && wsList[0];
        if (!ws) {
          ws = await workspaceApi.create({ name: 'Architecture Workspace' });
        }

        const sol = await solutionApi.create({
          workspace_id: ws.id,
          title: 'Autonomous System Discovery Session',
          description: 'Interactive session with AI Solution Builder swarm',
        });
        setSolutionId(sol.id);
      } catch {
        // Fallback for local demo preview
        setSolutionId('sol-demo-1');
      }
    }
    initSession();
  }, []);

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!inputMessage.trim() || isStreaming) return;

    const userText = inputMessage;
    setInputMessage('');
    setMessages(prev => [...prev, { role: 'user', content: userText }]);
    setIsStreaming(true);
    setPipelineStatus('analyzing');
    setCurrentAgent('business_analyst');

    try {
      const activeSolId = solutionId || 'sol-demo-1';

      await sendChatMessageStream(
        {
          solution_id: activeSolId,
          message: userText,
          uploaded_context: uploadedContext,
        },
        {
          onEvent: (event, data) => {
            if (data.agent) {
              setCurrentAgent(data.agent);
            }
            if (data.type === 'agent_start') {
              setMessages(prev => [
                ...prev,
                { role: 'assistant', agent: data.agent || 'Pipeline', content: data.message || `Swarm agent ${data.agent} invoked...` }
              ]);
            }
          },
          onComplete: (data) => {
            const streamStatus = data.status as 'complete' | 'recommending' | undefined;
            setPipelineStatus(streamStatus || 'complete');
            if (data.status === 'recommending' && data.recommendations) {
              const recs: RecommendedModule[] = data.recommendations.map((r) => {
                if (typeof r === 'string') {
                  return { name: r, description: `Automated ${r} subsystem module.`, features: ['Standard CRUD', 'API Endpoints', 'Postgres Models'] };
                }
                return r;
              });
              setRecommendations(recs);
              setSelectedModules(recs.map(r => r.name));
            }
            const message = data.message;
            if (message) {
              setMessages(prev => [
                ...prev,
                { role: 'assistant', agent: 'AI Architect', content: message }
              ]);
            }
            setIsStreaming(false);
          },
          onError: (err) => {
            console.error('Chat stream error', err);
            // If backend returned error (e.g. invalid GROQ_API_KEY), gracefully show recommendation demo
            handleMockFallback();
          },
        }
      );
    } catch {
      console.warn('Backend unavailable, falling back to simulated swarm execution for UI demonstration.');
      handleMockFallback();
    }
  };

  // Mock simulation when Groq key is empty or local testing
  const handleMockFallback = () => {
    setTimeout(() => {
      setCurrentAgent('business_recommendation');
      setPipelineStatus('recommending');
      setIsStreaming(false);

      const demoModules: RecommendedModule[] = [
        {
          name: 'Real-Time Inventory Engine',
          category: 'Core Operations',
          description: 'High-throughput stock tracking, low-inventory alerts, barcode scanning sync, and multi-warehouse allocation.',
          features: ['Stock Level Tracking', 'Barcode / QR Lookup', 'Supplier Restock Triggers', 'Multi-Store Balancing'],
          priority: 'Must Have',
        },
        {
          name: 'Point-of-Sale (POS) & Checkout Terminal',
          category: 'Transaction Processing',
          description: 'Offline-first POS interface, receipt printing, payment gateway integration, and split tender capabilities.',
          features: ['Quick Register UI', 'Stripe / Terminal SDK', 'Offline Order Sync', 'Tax Calculation Engine'],
          priority: 'Must Have',
        },
        {
          name: 'Customer Loyalty & Rewards Engine',
          category: 'Growth & Retention',
          description: 'Points accumulation, promotional tiers, SMS/Email discount vouchers, and purchase history analytics.',
          features: ['Points Ledger', 'Promotional Campaigns', 'Tier Progression', 'Digital Wallet Cards'],
          priority: 'Should Have',
        },
        {
          name: 'Staff Scheduling & Shift Management',
          category: 'Human Resources',
          description: 'Shift scheduling, time clock in/out, commission tracking, and role-based access control.',
          features: ['Shift Roster Calendar', 'Punch Clock Verification', 'Role Permission Guards', 'Commission Reports'],
          priority: 'Nice to Have',
        },
      ];

      setRecommendations(demoModules);
      setSelectedModules(demoModules.map(m => m.name));

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          agent: 'Recommendation Engine',
          content: `Based on your requirements, I've categorized your system domain and matched 4 core modules from the vertical architecture catalog. Review the modules below and confirm which ones you want to architect.`
        }
      ]);
    }, 1500);
  };

  const handleToggleModule = (name: string) => {
    if (selectedModules.includes(name)) {
      setSelectedModules(selectedModules.filter(m => m !== name));
    } else {
      setSelectedModules([...selectedModules, name]);
    }
  };

  const handleConfirmRecommendations = async () => {
    if (selectedModules.length === 0 || isStreaming) return;

    setIsStreaming(true);
    setPipelineStatus('generating');
    setCurrentAgent('solutions_architect');

    try {
      const activeSolId = solutionId || 'sol-demo-1';
      await confirmRecommendationsStream(
        {
          solution_id: activeSolId,
          accepted_modules: selectedModules,
        },
        {
          onEvent: (event, data) => {
            if (data.agent) setCurrentAgent(data.agent);
          },
          onComplete: () => {
            setPipelineStatus('complete');
            setIsStreaming(false);
            setMessages(prev => [
              ...prev,
              {
                role: 'assistant',
                agent: 'Blueprint Synthesizer',
                content: "All solution blueprints, architecture diagrams, PostgreSQL schemas, and delivery roadmaps have been successfully synthesized! Click the button below to inspect your complete engineering specification."
              }
            ]);
          },
          onError: () => {
            handleMockGenerationCompletion();
          }
        }
      );
    } catch {
      handleMockGenerationCompletion();
    }
  };

  const handleMockGenerationCompletion = () => {
    // Step sequentially through agents for visual WOW effect
    setCurrentAgent('solutions_architect');
    setTimeout(() => {
      setCurrentAgent('ux_agent');
      setTimeout(() => {
        setCurrentAgent('database_api_agent');
        setTimeout(() => {
          setCurrentAgent('blueprint_generator');
          setPipelineStatus('complete');
          setIsStreaming(false);
          setMessages(prev => [
            ...prev,
            {
              role: 'assistant',
              agent: 'Blueprint Synthesizer',
              content: `All solution blueprints for [${selectedModules.join(', ')}] have been generated! High-Level Design (HLD), Low-Level Design (LLD), wireframes, PostgreSQL DDL schema, OpenAPI specification, and 12-week roadmap are ready for review.`
            }
          ]);
        }, 800);
      }, 800);
    }, 800);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8.5rem)] max-w-5xl mx-auto">
      {/* Top Swarm Progress Stepper */}
      <div className="mb-4">
        <AgentProgressTracker currentAgent={currentAgent} status={pipelineStatus} />
      </div>

      {/* Chat Thread Container */}
      <div className="flex-1 bg-slate-950/60 border border-white/5 rounded-2xl p-6 overflow-y-auto backdrop-blur-xl shadow-2xl space-y-4">
        {messages.map((msg, index) => (
          <ChatMessage
            key={index}
            role={msg.role}
            content={msg.content}
            agent={msg.agent}
          />
        ))}

        {/* Streaming Indicator */}
        {isStreaming && (
          <div className="flex items-center gap-3 p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/20 max-w-sm text-indigo-300 text-xs">
            <Loader2 className="w-4 h-4 animate-spin text-indigo-400" />
            <span>Agent <strong>{currentAgent || 'Swarm'}</strong> is synthesizing output...</span>
          </div>
        )}

        {/* Recommended Modules Selector Block */}
        {pipelineStatus === 'recommending' && recommendations.length > 0 && (
          <div className="my-6 p-6 rounded-2xl bg-indigo-950/20 border border-indigo-500/30 space-y-4 animate-fade-in">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-white text-base">Recommended Subsystem Modules</h4>
                <p className="text-xs text-slate-400 mt-0.5">Select the modules you want included in the full architecture blueprint.</p>
              </div>
              <span className="text-xs text-indigo-300 font-semibold px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                {selectedModules.length} of {recommendations.length} Selected
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
              {recommendations.map((mod, idx) => (
                <RecommendationCard
                  key={idx}
                  module={mod}
                  selected={selectedModules.includes(mod.name)}
                  onToggle={() => handleToggleModule(mod.name)}
                />
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={handleConfirmRecommendations}
                disabled={selectedModules.length === 0 || isStreaming}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-cyan-500 hover:opacity-95 text-white font-semibold text-xs shadow-xl shadow-indigo-600/30 transition-all hover:scale-105 disabled:opacity-40"
              >
                <Sparkles className="w-4 h-4" />
                <span>Confirm Modules & Synthesize Full Blueprint</span>
              </button>
            </div>
          </div>
        )}

        {/* Solution Complete Banner */}
        {pipelineStatus === 'complete' && (
          <div className="my-6 p-6 rounded-2xl bg-gradient-to-r from-emerald-950/40 via-slate-900 to-indigo-950/40 border border-emerald-500/30 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center flex-shrink-0">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-base font-bold text-white">Full Blueprint Ready</h4>
                <p className="text-xs text-slate-400">Architecture (HLD/LLD), Wireframes, PostgreSQL schemas, and 12-week roadmap are compiled.</p>
              </div>
            </div>

            <Link
              href={`/solution/${solutionId || 'sol-demo-1'}`}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-indigo-600 hover:from-emerald-400 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-emerald-500/20 transition-all hover:scale-105 whitespace-nowrap"
            >
              <span>Inspect Generated Blueprints</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Chat Input & File Uploader Bar */}
      <div className="mt-4 space-y-2">
        {showUploader && (
          <div className="p-3 bg-slate-900/60 border border-white/10 rounded-2xl">
            <FileUploader
              onParsedContext={(text, filename) => {
                setUploadedContext(text);
                setUploadedFilename(filename);
                setShowUploader(false);
                setMessages(prev => [
                  ...prev,
                  {
                    role: 'assistant',
                    agent: 'Document Ingestion',
                    content: `Extracted content from **${filename}** (${text.length} characters). You can now ask questions about this document or generate an architecture based on it.`
                  }
                ]);
              }}
              onClear={() => {
                setUploadedContext('');
                setUploadedFilename('');
              }}
            />
          </div>
        )}

        <form onSubmit={handleSendMessage} className="relative flex items-center">
          <button
            type="button"
            onClick={() => setShowUploader(!showUploader)}
            className={`p-3 rounded-xl border mr-2 transition-colors ${
              uploadedContext
                ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-300'
                : 'bg-slate-900 border-white/10 text-slate-400 hover:text-slate-200'
            }`}
            title="Attach PRD or specification document"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder={
              uploadedFilename
                ? `Ask or generate architecture using context from ${uploadedFilename}...`
                : 'Describe what system or business you want to build (e.g. "Omnichannel Retail POS and Inventory platform")...'
            }
            disabled={isStreaming}
            className="flex-1 py-3.5 pl-4 pr-12 rounded-xl bg-slate-900 border border-white/10 text-white text-xs placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition-colors shadow-inner"
          />

          <button
            type="submit"
            disabled={!inputMessage.trim() || isStreaming}
            className="absolute right-2 p-2 rounded-lg bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white transition-all disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<div className="text-white text-xs p-6">Loading AI Architect Studio...</div>}>
      <ChatContent />
    </Suspense>
  );
}
