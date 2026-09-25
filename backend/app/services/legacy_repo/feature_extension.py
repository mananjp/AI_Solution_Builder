"""
AI Solution Builder — Feature Extension Engine (AI Chatbot, Search, RAG)

Integrates user-requested capabilities into the legacy application's existing
architecture without spawning unnecessary parallel services or breaking existing routes.
"""

import logging
from pathlib import Path
from typing import Any

from app.services.legacy_repo.boundary import assert_safe_boundary

logger = logging.getLogger(__name__)


class FeatureExtensionEngine:
    """Injects requested capabilities into existing backend and frontend frameworks."""

    def __init__(self, repo_dir: Path | str, tech_stack: dict[str, Any], entry_points: dict[str, Any]):
        self.root = assert_safe_boundary(repo_dir, action="extend features in")
        self.stack = tech_stack
        self.entry_points = entry_points

    def add_ai_chatbot(
        self,
        *,
        provider: str = "groq",
        model: str = "llama-3.3-70b-versatile",
        chat_route_prefix: str = "/api/chat",
    ) -> list[str]:
        """Integrate an AI Chatbot endpoint and frontend UI directly into the existing repository.

        Returns list of newly created or modified files.
        """
        modified_files: list[str] = []

        be_entry_str = str(self.entry_points.get("backend_entry") or "")
        fe_entry_str = str(self.entry_points.get("frontend_entry") or "")

        is_python_be = "Python" in self.stack.get("languages", []) or be_entry_str.endswith(".py")
        is_node_be = "JavaScript" in self.stack.get("languages", []) or "TypeScript" in self.stack.get("languages", [])
        is_react_fe = bool(self.stack.get("frontend_framework")) or fe_entry_str.endswith((".tsx", ".jsx"))

        # 1. Backend Service Extension
        if is_python_be:
            backend_files = self._inject_python_chat_service(provider, model)
            modified_files.extend(backend_files)
        elif is_node_be:
            backend_files = self._inject_node_chat_service(provider, model)
            modified_files.extend(backend_files)
        else:
            # Fallback lightweight Python ASGI chat micro-route if no backend detected
            backend_files = self._inject_python_chat_service(provider, model)
            modified_files.extend(backend_files)

        # 2. Frontend Chat UI Extension
        if is_react_fe:
            frontend_files = self._inject_react_chat_ui(chat_route_prefix)
            modified_files.extend(frontend_files)
        else:
            frontend_files = self._inject_vanilla_chat_ui(chat_route_prefix)
            modified_files.extend(frontend_files)

        return modified_files

    # ── Python Backend Injection ──────────────────────────────────────────

    def _inject_python_chat_service(self, provider: str, model: str) -> list[str]:
        """Inject chat service and router into FastAPI, Flask, or standard Python backend."""
        modified: list[str] = []

        # Find backend directory or use root
        be_entry = self.entry_points.get("backend_entry")
        target_dir = self.root / (Path(be_entry).parent if be_entry else "")

        chat_module_path = target_dir / "chat_service.py"
        chat_code = f'''"""
AI Chat Service — Integrated into legacy backend
"""
import os
import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

PROVIDER = "{provider}"
MODEL = "{model}"

async def generate_chat_response(messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> str:
    """Generate completion using configured LLM provider and API key from environment."""
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        return "AI Chatbot is configured, but no API key was found in the environment. Please add GROQ_API_KEY to your .env file."

    effective_messages = []
    if system_prompt:
        effective_messages.append({{"role": "system", "content": system_prompt}})
    else:
        effective_messages.append({{
            "role": "system",
            "content": "You are a helpful, professional AI assistant integrated directly into this application."
        }})
    effective_messages.extend(messages)

    headers = {{
        "Authorization": f"Bearer {{api_key}}",
        "Content-Type": "application/json"
    }}
    
    # Provider endpoint
    endpoint = "https://api.groq.com/openai/v1/chat/completions" if "groq" in PROVIDER.lower() else "https://api.openai.com/v1/chat/completions"
    
    payload = {{
        "model": MODEL if "groq" in PROVIDER.lower() else "gpt-4o-mini",
        "messages": effective_messages,
        "temperature": 0.7,
        "max_tokens": 1024
    }}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error("LLM API returned error: %d - %s", resp.status_code, resp.text)
                return f"Error contacting AI service (HTTP {{resp.status_code}}). Please check API key status."
    except Exception as exc:
        logger.exception("Chat completion error: %s", exc)
        return f"Unable to reach AI service: {{str(exc)}}"
'''
        chat_module_path.write_text(chat_code, encoding="utf-8")
        rel_chat = str(chat_module_path.relative_to(self.root)).replace("\\", "/")
        modified.append(rel_chat)

        # Check if FastAPI or Flask router can be added
        fastapi_route_code = '''
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
try:
    from .chat_service import generate_chat_response
except ImportError:
    from chat_service import generate_chat_response

chat_router = APIRouter(prefix="/api/chat", tags=["AI Chatbot"])

class ChatPayload(BaseModel):
    messages: List[Dict[str, str]]
    system_prompt: Optional[str] = None

@chat_router.post("/")
async def chat_endpoint(payload: ChatPayload):
    try:
        reply = await generate_chat_response(payload.messages, payload.system_prompt)
        return {"response": reply, "status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
'''
        router_path = target_dir / "chat_router.py"
        router_path.write_text(fastapi_route_code, encoding="utf-8")
        rel_router = str(router_path.relative_to(self.root)).replace("\\", "/")
        modified.append(rel_router)

        # Mount into main entry point if present
        if be_entry and (self.root / be_entry).exists():
            entry_file = self.root / be_entry
            content = entry_file.read_text(encoding="utf-8", errors="ignore")
            if "chat_router" not in content and "FastAPI" in content:
                mount_snippet = "\n# AI Chatbot Extension Route\ntry:\n    from chat_router import chat_router\n    app.include_router(chat_router)\nexcept Exception as _e:\n    pass\n"
                entry_file.write_text(content + mount_snippet, encoding="utf-8")
                modified.append(str(Path(be_entry)).replace("\\", "/"))

        return modified

    # ── Node.js Backend Injection ─────────────────────────────────────────

    def _inject_node_chat_service(self, provider: str, model: str) -> list[str]:
        """Inject Express or Next.js API route for chat."""
        modified: list[str] = []
        is_next = "next" in str(self.stack.get("frontend_framework", "")).lower()

        if is_next:
            api_route_dir = self.root / "src" / "app" / "api" / "chat"
            if not api_route_dir.exists():
                api_route_dir = self.root / "app" / "api" / "chat"
            api_route_dir.mkdir(parents=True, exist_ok=True)
            route_ts = api_route_dir / "route.ts"
            route_code = f'''import {{ NextResponse }} from 'next/server';

export async function POST(req: Request) {{
  try {{
    const body = await req.json();
    const {{ messages, systemPrompt }} = body;
    const apiKey = process.env.GROQ_API_KEY || process.env.OPENAI_API_KEY;

    if (!apiKey) {{
      return NextResponse.json({{
        response: "AI Chatbot is configured, but no API key was found. Please set GROQ_API_KEY in your environment.",
        status: "missing_key"
      }}, {{ status: 200 }});
    }}

    const endpoint = "https://api.groq.com/openai/v1/chat/completions";
    const effectiveMessages = [
      {{ role: "system", content: systemPrompt || "You are a helpful assistant integrated into this web application." }},
      ...(messages || [])
    ];

    const resp = await fetch(endpoint, {{
      method: "POST",
      headers: {{
        "Authorization": `Bearer ${{apiKey}}`,
        "Content-Type": "application/json"
      }},
      body: JSON.stringify({{
        model: "{model}",
        messages: effectiveMessages,
        temperature: 0.7,
        max_tokens: 1024
      }})
    }});

    if (!resp.ok) {{
      const errText = await resp.text();
      return NextResponse.json({{ response: `AI service error: ${{resp.status}}`, detail: errText }}, {{ status: 500 }});
    }}

    const data = await resp.json();
    const reply = data.choices?.[0]?.message?.content || "No response received";
    return NextResponse.json({{ response: reply, status: "success" }});
  }} catch (err: any) {{
    return NextResponse.json({{ response: `Error: ${{err?.message || err}}` }}, {{ status: 500 }});
  }}
}}
'''
            route_ts.write_text(route_code, encoding="utf-8")
            modified.append(str(route_ts.relative_to(self.root)).replace("\\", "/"))
        else:
            # Express router
            routes_dir = self.root / "routes"
            routes_dir.mkdir(parents=True, exist_ok=True)
            chat_js = routes_dir / "chat.js"
            chat_code = f'''const express = require('express');
const router = express.Router();

router.post('/', async (req, res) => {{
  try {{
    const {{ messages, systemPrompt }} = req.body;
    const apiKey = process.env.GROQ_API_KEY || process.env.OPENAI_API_KEY;
    if (!apiKey) {{
      return res.json({{ response: "GROQ_API_KEY is not configured.", status: "missing_key" }});
    }}
    const effectiveMessages = [
      {{ role: "system", content: systemPrompt || "You are a helpful assistant." }},
      ...(messages || [])
    ];
    const fetch = (...args) => import('node-fetch').then(({{default: f}}) => f(...args));
    const apiRes = await fetch("https://api.groq.com/openai/v1/chat/completions", {{
      method: "POST",
      headers: {{
        "Authorization": `Bearer ${{apiKey}}`,
        "Content-Type": "application/json"
      }},
      body: JSON.stringify({{
        model: "{model}",
        messages: effectiveMessages
      }})
    }});
    const data = await apiRes.json();
    const reply = data.choices?.[0]?.message?.content || "No reply";
    res.json({{ response: reply, status: "success" }});
  }} catch (err) {{
    res.status(500).json({{ error: err.message }});
  }}
}});

module.exports = router;
'''
            chat_js.write_text(chat_code, encoding="utf-8")
            modified.append(str(chat_js.relative_to(self.root)).replace("\\", "/"))

        return modified

    # ── React Chat UI Injection ───────────────────────────────────────────

    def _inject_react_chat_ui(self, chat_route_prefix: str) -> list[str]:
        """Inject an animated, responsive AI Chatbot widget component for React/Next."""
        modified: list[str] = []
        if (self.root / "src").exists():
            components_dir = self.root / "src" / "components"
        else:
            components_dir = self.root / "components"
        components_dir.mkdir(parents=True, exist_ok=True)

        widget_file = components_dir / "AIChatbotWidget.tsx"
        widget_code = f'''"use client";

import React, {{ useState, useRef, useEffect }} from 'react';

interface ChatMessage {{
  role: 'user' | 'assistant';
  content: string;
}}

export default function AIChatbotWidget() {{
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {{ role: 'assistant', content: 'Hello! I am your AI assistant. How can I help you with this application today?' }}
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {{
    messagesEndRef.current?.scrollIntoView({{ behavior: 'smooth' }});
  }};

  useEffect(() => {{
    if (isOpen) scrollToBottom();
  }}, [messages, isOpen]);

  const handleSend = async (e: React.FormEvent) => {{
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: ChatMessage = {{ role: 'user', content: input.trim() }};
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);

    try {{
      const res = await fetch('{chat_route_prefix}', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ messages: updatedMessages }}),
      }});
      const data = await res.json();
      const reply = data.response || 'No response from assistant.';
      setMessages([...updatedMessages, {{ role: 'assistant', content: reply }}]);
    }} catch (err) {{
      setMessages([
        ...updatedMessages,
        {{ role: 'assistant', content: 'Could not connect to the chat service. Please check your backend.' }}
      ]);
    }} finally {{
      setLoading(false);
    }}
  }};

  return (
    <div style={{{{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999, fontFamily: 'inherit' }}}}>
      {{!isOpen ? (
        <button
          onClick={{() => setIsOpen(true)}}
          style={{{{
            backgroundColor: '#0f172a',
            color: '#ffffff',
            padding: '12px 20px',
            borderRadius: '9999px',
            border: '1px solid rgba(255,255,255,0.1)',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            fontWeight: 600,
            fontSize: '14px',
            transition: 'transform 0.2s',
          }}}}
        >
          <span style={{{{ fontSize: '18px' }}}}>✨</span>
          <span>Ask AI Assistant</span>
        </button>
      ) : (
        <div
          style={{{{
            width: '360px',
            height: '500px',
            backgroundColor: '#ffffff',
            color: '#0f172a',
            borderRadius: '16px',
            boxShadow: '0 20px 35px -10px rgba(0, 0, 0, 0.25)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            border: '1px solid #e2e8f0',
          }}}}
        >
          {{/* Header */}}
          <div
            style={{{{
              padding: '14px 16px',
              backgroundColor: '#0f172a',
              color: '#ffffff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}}}
          >
            <div style={{{{ display: 'flex', alignItems: 'center', gap: '8px' }}}}>
              <span style={{{{ fontSize: '16px' }}}}>✨</span>
              <strong style={{{{ fontSize: '14px' }}}}>AI Assistant</strong>
            </div>
            <button
              onClick={{() => setIsOpen(false)}}
              style={{{{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '16px' }}}}
            >
              ✕
            </button>
          </div>

          {{/* Messages Body */}}
          <div style={{{{ flex: 1, padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}}}>
            {{messages.map((m, idx) => (
              <div
                key={{idx}}
                style={{{{
                  alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
                  backgroundColor: m.role === 'user' ? '#3b82f6' : '#f1f5f9',
                  color: m.role === 'user' ? '#ffffff' : '#1e293b',
                  padding: '10px 14px',
                  borderRadius: '12px',
                  maxWidth: '82%',
                  fontSize: '13px',
                  lineHeight: '1.4',
                  whiteSpace: 'pre-wrap',
                }}}}
              >
                {{m.content}}
              </div>
            ))}}
            {{loading && (
              <div style={{{{ alignSelf: 'flex-start', color: '#64748b', fontSize: '12px', fontStyle: 'italic' }}}}>
                AI assistant is typing...
              </div>
            )}}
            <div ref={{messagesEndRef}} />
          </div>

          {{/* Input Form */}}
          <form
            onSubmit={{handleSend}}
            style={{{{ padding: '12px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '8px' }}}}
          >
            <input
              type="text"
              value={{input}}
              onChange={{(e) => setInput(e.target.value)}}
              placeholder="Ask anything..."
              style={{{{
                flex: 1,
                padding: '8px 12px',
                border: '1px solid #cbd5e1',
                borderRadius: '8px',
                fontSize: '13px',
                outline: 'none',
              }}}}
            />
            <button
              type="submit"
              disabled={{loading}}
              style={{{{
                padding: '8px 14px',
                backgroundColor: '#3b82f6',
                color: '#ffffff',
                border: 'none',
                borderRadius: '8px',
                fontWeight: 600,
                fontSize: '13px',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}}}
            >
              Send
            </button>
          </form>
        </div>
      )}}
    </div>
  );
}}
'''
        widget_file.write_text(widget_code, encoding="utf-8")
        rel_w = str(widget_file.relative_to(self.root)).replace("\\", "/")
        modified.append(rel_w)

        return modified

    # ── Vanilla Chat UI Injection ─────────────────────────────────────────

    def _inject_vanilla_chat_ui(self, chat_route_prefix: str) -> list[str]:
        """Inject lightweight vanilla JS widget for legacy static/HTML applications."""
        public_dir = self.root / "public"
        if not public_dir.exists():
            public_dir = self.root / "static"
        if not public_dir.exists():
            public_dir = self.root
        public_dir.mkdir(parents=True, exist_ok=True)

        widget_js = public_dir / "ai_chat_widget.js"
        code = f'''// Standalone AI Chat Widget for Legacy Applications
(function() {{
  const chatButton = document.createElement('button');
  chatButton.innerHTML = '✨ Ask AI';
  chatButton.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9999;padding:10px 18px;background:#0f172a;color:#fff;border-radius:24px;border:none;box-shadow:0 4px 12px rgba(0,0,0,0.2);cursor:pointer;font-weight:bold;';
  document.body.appendChild(chatButton);
  chatButton.onclick = () => alert("AI Chatbot endpoint available at {chat_route_prefix}");
}})();
'''
        widget_js.write_text(code, encoding="utf-8")
        return [str(widget_js.relative_to(self.root)).replace("\\", "/")]
