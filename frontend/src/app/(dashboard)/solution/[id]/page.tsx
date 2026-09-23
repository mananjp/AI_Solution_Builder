'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Download,
  Clock,
  CheckCircle2,
  MessageSquare,
  Rocket,
  ShieldCheck,
  AlertCircle,
  HelpCircle,
  GitBranch,
} from 'lucide-react';
import ArtifactViewer from '@/components/ArtifactViewer';
import ExportModal from '@/components/ExportModal';
import { GuidedStepper, StageKey } from '@/components/GuidedStepper';
import { WhatYouMissedPanel, MissingRequirement, OpenQuestion } from '@/components/WhatYouMissedPanel';
import { ExplainabilityDrawer } from '@/components/ExplainabilityDrawer';
import { ImpactPreviewModal } from '@/components/ImpactPreviewModal';
import { solutionApi } from '@/lib/api';
import { Solution, Artifact } from '@/types';

export default function SolutionViewerPage() {
  const params = useParams();
  const solutionId = params?.id as string;

  const [solution, setSolution] = useState<Solution | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [showExportModal, setShowExportModal] = useState(false);

  // Approval & Explainability States
  const [isApproving, setIsApproving] = useState(false);
  const [showChangesModal, setShowChangesModal] = useState(false);
  const [changeComments, setChangeComments] = useState('');
  const [isSubmittingChanges, setIsSubmittingChanges] = useState(false);
  const [explainArtifactId, setExplainArtifactId] = useState<string | null>(null);
  const [impactArtifact, setImpactArtifact] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  useEffect(() => {
    async function loadSolution() {
      try {
        const sol = await solutionApi.get(solutionId);
        setSolution(sol);
        if (sol.artifacts && sol.artifacts.length > 0) {
          setArtifacts(sol.artifacts);
        } else {
          setArtifacts(getSampleArtifacts(sol.title));
        }
      } catch {
        const sampleSol: Solution = {
          id: solutionId,
          workspace_id: 'ws-demo-1',
          title: 'Omnichannel Retail POS & Inventory Platform',
          description:
            'Enterprise architecture with real-time stock sync, offline POS, loyalty rewards, and role-based staff scheduling.',
          status: 'complete',
          approval_status: 'pending',
          created_at: new Date().toISOString(),
          ai_state: {
            requirements: [
              {
                id: 'req-dpdp',
                kind: 'compliance',
                text: 'Digital Personal Data Protection (DPDP) Act compliance for customer consent & data retention',
                status: 'missing',
                priority: 'must',
              },
              {
                id: 'req-offline',
                kind: 'nfr',
                text: 'Offline transaction queue with HMAC signature and automatic reconcile on reconnection',
                status: 'suggested',
                priority: 'must',
              },
            ],
            open_questions: [
              {
                id: 'q-tax',
                question: 'What GST/VAT tax slab configuration should be default across retail branches?',
                category: 'compliance',
                why_it_matters: 'Affects invoice generation schema and payment gateway tax breakdown rules.',
                suggested_answers: ['Single flat GST 18%', 'Multi-tier GST (5%, 12%, 18%, 28%)', 'Tax-exempt'],
              },
            ],
          },
        };
        setSolution(sampleSol);
        setArtifacts(getSampleArtifacts(sampleSol.title));
      }
    }

    loadSolution();
  }, [solutionId]);

  const handleApprove = async () => {
    if (!solution) return;
    setIsApproving(true);
    setActionNotice(null);
    try {
      const res = await solutionApi.approve(solution.id);
      setSolution((prev) =>
        prev
          ? {
              ...prev,
              status: 'approved',
              approval_status: 'approved',
              approved_at: res.approved_at,
            }
          : prev
      );
      setActionNotice('Blueprint approved and artifact snapshot frozen! MVP build is now unlocked.');
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: string }).message)
          : 'Approval failed.';
      setActionNotice(`Error: ${msg}`);
    } finally {
      setIsApproving(false);
    }
  };

  const handleRequestChanges = async () => {
    if (!solution || !changeComments.trim()) return;
    setIsSubmittingChanges(true);
    try {
      await solutionApi.requestChanges(solution.id, changeComments);
      setSolution((prev) =>
        prev
          ? {
              ...prev,
              status: 'changes_requested',
              approval_status: 'changes_requested',
            }
          : prev
      );
      setShowChangesModal(false);
      setChangeComments('');
      setActionNotice('Changes requested. The architecture team / AI agents will review feedback.');
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'message' in err
          ? String((err as { message: string }).message)
          : 'Request failed.';
      setActionNotice(`Error: ${msg}`);
    } finally {
      setIsSubmittingChanges(false);
    }
  };

  // Determine Stepper Stage
  const isApproved = solution?.approval_status === 'approved' || solution?.status === 'approved';
  let currentStage: StageKey = 'blueprint';
  const completedStages: StageKey[] = ['input', 'clarify'];

  if (isApproved) {
    currentStage = 'approve';
    completedStages.push('blueprint', 'approve');
  } else if (solution?.status === 'clarifying') {
    currentStage = 'clarify';
  } else if (solution?.status === 'draft') {
    currentStage = 'input';
  }

  // Extract missing requirements and questions from AI state
  const aiState = (solution?.ai_state || {}) as Record<string, unknown>;
  const missingRequirements: MissingRequirement[] = Array.isArray(aiState.requirements)
    ? (aiState.requirements as MissingRequirement[]).filter((r) => r.status === 'missing' || r.status === 'suggested')
    : [];
  const openQuestions: OpenQuestion[] = Array.isArray(aiState.open_questions)
    ? (aiState.open_questions as OpenQuestion[])
    : [];

  return (
    <div className="space-y-6 max-w-[1400px] mx-auto animate-fade-up">
      {/* 1. Guided Stepper across top */}
      <GuidedStepper
        currentStage={currentStage}
        completedStages={completedStages}
      />

      {/* Action Notice Toast */}
      {actionNotice && (
        <div className="p-3 rounded-lg text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 flex items-center justify-between">
          <span>{actionNotice}</span>
          <button
            onClick={() => setActionNotice(null)}
            className="text-slate-400 hover:text-white text-xs px-2"
          >
            ✕
          </button>
        </div>
      )}

      {/* Navigation & Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-[11px] uppercase tracking-widest font-semibold text-[var(--text-2)] hover:text-[var(--sutra-charcoal)] transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Explainability / Why? Drawer Trigger */}
          <button
            onClick={() => setExplainArtifactId(artifacts[0]?.id || 'sample-hld')}
            className="btn btn-ghost border border-[var(--border)] bg-[var(--bg)] flex items-center gap-1.5"
            title="Inspect architectural decisions, evidence, and assumptions log"
          >
            <HelpCircle className="w-3.5 h-3.5 text-indigo-400" />
            <span>Why? (Decision Log)</span>
          </button>

          {/* Cascade Impact Preview */}
          <button
            onClick={() => setImpactArtifact('hld')}
            className="btn btn-ghost border border-[var(--border)] bg-[var(--bg)] flex items-center gap-1.5"
            title="Preview cascading impact before regenerating artifacts"
          >
            <GitBranch className="w-3.5 h-3.5 text-amber-400" />
            <span>Impact Preview</span>
          </button>

          <Link
            href={`/solution/${solutionId}/mvp`}
            className={`btn ${isApproved ? 'btn-primary shadow-lg shadow-indigo-500/20' : 'btn-secondary'} flex items-center gap-1.5`}
          >
            <Rocket className="w-3.5 h-3.5" />
            <span>Build &amp; Deploy MVP</span>
          </Link>

          <Link
            href={`/solution/${solutionId}/mvp`}
            className="btn btn-ghost border border-[var(--border)] bg-[var(--bg)]"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chat with AI Architect</span>
          </Link>

          <button
            onClick={() => setShowExportModal(true)}
            className="btn btn-ghost border border-[var(--border)] bg-[var(--bg)]"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Package</span>
          </button>
        </div>
      </div>

      {/* Solution Header Card with Approval Gate */}
      <div className="sutra-card p-6 bg-[var(--bg-2)] flex flex-col md:flex-row md:items-center justify-between gap-6 border border-[var(--border)]">
        <div className="space-y-3 flex-1">
          <div className="flex flex-wrap items-center gap-3 text-[10px] uppercase tracking-widest font-semibold">
            {isApproved ? (
              <span className="badge badge-green flex items-center gap-1.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                Blueprint Approved &amp; Locked
              </span>
            ) : solution?.approval_status === 'changes_requested' ? (
              <span className="badge flex items-center gap-1.5 bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <AlertCircle className="w-3 h-3 text-amber-400" />
                Changes Requested
              </span>
            ) : (
              <span className="badge flex items-center gap-1.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Clock className="w-3 h-3 text-indigo-400" />
                Pending Sign-Off Gate
              </span>
            )}
            <span className="text-[var(--text-3)]">|</span>
            <span className="text-[var(--text-2)] flex items-center gap-1.5">
              <Clock className="w-3 h-3" />
              {solution?.created_at ? new Date(solution.created_at).toLocaleDateString() : 'Today'}
            </span>
          </div>

          <h1 className="text-2xl font-serif text-[var(--sutra-charcoal)]">{solution?.title}</h1>
          <p className="text-[13px] text-[var(--text-2)] max-w-4xl leading-relaxed font-light">
            {solution?.description}
          </p>
        </div>

        {/* Approval Gate Control Panel */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 p-3 rounded-xl bg-slate-900/50 border border-slate-800">
          {!isApproved ? (
            <>
              <button
                onClick={handleApprove}
                disabled={isApproving}
                className="btn btn-primary bg-emerald-600 hover:bg-emerald-500 text-white flex items-center justify-center gap-1.5 text-xs font-semibold px-4 py-2"
              >
                <ShieldCheck className="w-4 h-4" />
                <span>{isApproving ? 'Approving...' : 'Approve Blueprint'}</span>
              </button>
              <button
                onClick={() => setShowChangesModal(true)}
                className="btn btn-ghost border border-slate-700 hover:bg-slate-800 text-xs font-medium px-3 py-2 text-slate-300"
              >
                Request Changes
              </button>
            </>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-emerald-400 font-mono">
              <ShieldCheck className="w-4 h-4" />
              <span>Snapshot Frozen • Ready for Build</span>
            </div>
          )}
        </div>
      </div>

      {/* 2. What You Missed Panel (Architecture & Compliance Gaps) */}
      <WhatYouMissedPanel
        missingRequirements={missingRequirements}
        openQuestions={openQuestions}
      />

      {/* Deep Artifact Viewer */}
      <div className="h-[750px] sutra-card shadow-lg bg-[var(--bg-2)] p-2">
        <ArtifactViewer
          artifacts={artifacts}
          solutionId={solutionId}
          onArtifactUpdated={(newArt) => {
            setArtifacts([
              newArt,
              ...artifacts.filter(
                (a) => a.id !== newArt.id && a.artifact_type !== newArt.artifact_type
              ),
            ]);
          }}
        />
      </div>

      {/* Export Modal */}
      <ExportModal
        solutionId={solutionId}
        solutionTitle={solution?.title || 'Solution'}
        isOpen={showExportModal}
        onClose={() => setShowExportModal(false)}
      />

      {/* Explainability Drawer */}
      <ExplainabilityDrawer
        artifactId={explainArtifactId || ''}
        isOpen={Boolean(explainArtifactId)}
        onClose={() => setExplainArtifactId(null)}
      />

      {/* Impact Preview Modal */}
      <ImpactPreviewModal
        isOpen={Boolean(impactArtifact)}
        solutionId={solutionId}
        targetArtifact={impactArtifact || 'hld'}
        onClose={() => setImpactArtifact(null)}
        onConfirmRegenerate={async () => {
          setImpactArtifact(null);
          setActionNotice('Regeneration dispatched with cascade dependency tracking.');
        }}
      />

      {/* Request Changes Modal */}
      {showChangesModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-6 shadow-2xl text-slate-100 space-y-4">
            <h3 className="text-base font-semibold text-white">Request Changes on Blueprint</h3>
            <p className="text-xs text-slate-400">
              Provide feedback for the solution architects and agents to refine the architecture:
            </p>
            <textarea
              value={changeComments}
              onChange={(e) => setChangeComments(e.target.value)}
              placeholder="e.g. Add multi-tenant row-level security, switch database to PostgreSQL with pgvector, and specify SMS notification provider..."
              rows={4}
              className="w-full rounded-xl bg-slate-950 border border-slate-800 p-3 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-hidden focus:border-indigo-500"
            />
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowChangesModal(false)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRequestChanges}
                disabled={isSubmittingChanges || !changeComments.trim()}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50"
              >
                {isSubmittingChanges ? 'Submitting...' : 'Submit Request'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function getSampleArtifacts(title: string): Artifact[] {
  return [
    {
      id: 'art-hld',
      solution_id: 'sample',
      artifact_type: 'hld',
      title: 'High-Level System Architecture (HLD)',
      version: 1,
      created_at: new Date().toISOString(),
      content: {},
      content_text: `# High-Level Architecture Design (HLD)

**System:** ${title}  
**Target Scale:** Enterprise / 100,000+ Daily Active Users

---

## 1. System Topology & Deployment Architecture

### Client Layer
- **Web App:** Next.js 15, React 19, Tailwind CSS
- **Mobile POS Terminal PWA:** Offline IndexedDB, Barcode Camera Engine
- **Admin & Analytics Portal:** Real-time WebSockets Dashboard

### Edge & Ingress
- **CDN:** Cloudflare Global CDN / DDoS Mitigation
- **API Gateway:** Traefik API Gateway with JWT validation, rate limiting (Redis token bucket)

### Microservices / Subsystems (Containerized via Alpine Docker)
- **API Gateway & Auth:** Python FastAPI, OAuth2, RBAC
- **Inventory Engine:** Async event bus, Low-Stock alerts
- **POS & Checkout Engine:** Stripe Terminal SDK, idempotency keys
- **Loyalty Engine:** Tier evaluation, points ledger

### Persistence Layer
- **Database:** PostgreSQL 16 (PgBouncer connection pooling)
- **Cache Store:** Redis cluster (In-memory)
- **Object Storage:** S3 / MinIO for receipts & PDFs

---

## 2. Security & Compliance Posture
- **Data-at-Rest:** AES-256 encrypted volumes
- **Data-in-Transit:** TLS 1.3 strict transport security
- **Authentication:** JWT tokens with 24h expiration, refresh rotation
- **Authorization:** Strict RBAC: Admin, Store Manager, Cashier, Customer
- **Audit Trail:** Immutable append logs for all financial mutations

---

## 3. Resilience & Disaster Recovery
- **Target SLO:** 99.95% Availability (< 4.38 hours downtime/year)
- **PITR Recovery:** WAL archiving (RPO < 5 mins, RTO < 30 mins)
- **Offline-first POS:** Terminal sync queue for offline transaction processing
`,
    },
    {
      id: 'art-lld',
      solution_id: 'sample',
      artifact_type: 'lld',
      title: 'Low-Level Technical Design & Component Specs (LLD)',
      version: 1,
      created_at: new Date().toISOString(),
      content: {},
      content_text: `# Low-Level Technical Design (LLD)

## 1. Inventory Subsystem Class Specification

\`\`\`python
class StockAdjustmentService:
    def __init__(self, db_session: AsyncSession, event_bus: EventBus):
        self.db = db_session
        self.events = event_bus

    async def deduct_inventory(self, store_id: UUID, sku: str, quantity: int, transaction_id: UUID):
        async with self.db.begin():
            # Pessimistic row locking to prevent double-sells
            item = await self.db.execute(
                select(InventoryItem)
                .where(InventoryItem.store_id == store_id, InventoryItem.sku == sku)
                .with_for_update()
            )
            if not item or item.available_quantity < quantity:
                raise InsufficientStockError(f"SKU {sku} has insufficient stock")
            
            item.available_quantity -= quantity
            item.reserved_quantity += quantity
            
            if item.available_quantity <= item.reorder_threshold:
                await self.events.publish("inventory.low_stock", {"sku": sku, "remaining": item.available_quantity})
\`\`\`

## 2. Idempotency & Offline Resolution

1. POS terminals generate a UUIDv4 \`client_transaction_id\` locally.
2. On reconnect, POS posts batch of transactions with client timestamps and UUIDs.
3. Gateway executes atomic insertion into PostgreSQL:
   \`\`\`sql
   INSERT INTO sales_orders (id, store_id, total_amount) VALUES (...) ON CONFLICT (id) DO NOTHING;
   \`\`\`
`,
    },
    {
      id: 'art-schema',
      solution_id: 'sample',
      artifact_type: 'database_schema',
      title: 'PostgreSQL Relational Schema & DDL',
      version: 1,
      created_at: new Date().toISOString(),
      content: {},
      content_text: `# PostgreSQL 16 DDL Schema

\`\`\`sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    plan_tier VARCHAR(50) DEFAULT 'enterprise',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Stores / Branches
CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Product Catalog
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    sku VARCHAR(100) NOT NULL,
    barcode VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    retail_price NUMERIC(10, 2) NOT NULL,
    cost_price NUMERIC(10, 2) NOT NULL,
    category VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_org_sku UNIQUE (org_id, sku)
);
CREATE INDEX idx_products_sku ON products(sku);
CREATE INDEX idx_products_barcode ON products(barcode);
\`\`\`
`,
    },
    {
      id: 'art-api',
      solution_id: 'sample',
      artifact_type: 'api_spec',
      title: 'OpenAPI 3.0 Specification',
      version: 1,
      created_at: new Date().toISOString(),
      content: {},
      content_text: `\`\`\`yaml
openapi: 3.0.3
info:
  title: Solution Core REST API
  description: High-throughput API for Retail POS & Stock Sync
  version: 1.0.0
paths:
  /api/v1/pos/checkout:
    post:
      summary: Submit POS order with idempotency
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [idempotency_key, store_id, items, payment_method]
              properties:
                idempotency_key: { type: string, format: uuid }
                store_id: { type: string, format: uuid }
                payment_method: { type: string, enum: [cash, card, qr_code] }
      responses:
        '201':
          description: Order processed successfully
\`\`\`
`,
    },
    {
      id: 'art-roadmap',
      solution_id: 'sample',
      artifact_type: 'roadmap',
      title: '12-Week Implementation Roadmap',
      version: 1,
      created_at: new Date().toISOString(),
      content: {},
      content_text: `# 12-Week Engineering Delivery Roadmap

## Phase 1: Foundation & Data Architecture (Weeks 1 - 3)
- **Milestone 1.1:** Deploy PostgreSQL schemas, triggers, and migrations (Week 1)
- **Milestone 1.2:** Core FastAPI authentication, RBAC, and multi-tenancy (Week 2)
- **Milestone 1.3:** Product catalog & store setup APIs (Week 3)

## Phase 2: Inventory Engine & Sync (Weeks 4 - 6)
- **Milestone 2.1:** Stock adjustment service with pessimistic row locks (Week 4)
- **Milestone 2.2:** Barcode & QR code scanning integration (Week 5)
- **Milestone 2.3:** Supplier restock alerts & purchase order flows (Week 6)

## Phase 3: POS Terminal & Checkout (Weeks 7 - 9)
- **Milestone 3.1:** Offline-first IndexedDB cache & UI (Week 7)
- **Milestone 3.2:** Stripe Terminal SDK / Card payment integration (Week 8)
- **Milestone 3.3:** Idempotent transaction reconciliation engine (Week 9)
`,
    },
    {
      id: 'art-wireframe',
      solution_id: 'sample',
      artifact_type: 'wireframe',
      title: 'Point-of-Sale (POS) Fast-Checkout Wireframe',
      version: 1,
      created_at: new Date().toISOString(),
      content: {
        description: 'Dual-pane POS terminal with touch-friendly catalog on left and checkout receipt slip on right.',
        components: [
          'Barcode Scanner Bar',
          'Quick Category Tabs',
          'Product Grid',
          'Cart Bill Summary',
          'Payment Buttons',
        ],
      },
      content_text: `# POS Fast-Checkout Terminal

\`\`\`
+-----------------------------------------------------------------------------+
| [=] STORE #104 - REGISTER 02         Cashier: Sarah Chen   [Offline Status] |
+------------------------------------------------------+----------------------+
| [Search by SKU or Scan Barcode...                 ] | CURRENT SALE (#8941) |
+------------------------------------------------------+----------------------+
| [All] [Beverages] [Bakery] [Produce] [Snacks]        | 1x Artisan Sourdough |
|                                                      |    $4.50             |
| +------------------+ +------------------+            | 2x Cold Brew 12oz    |
| | Artisan Sourdough| | Cold Brew Coffee |            |    $7.00 ($3.50 ea)  |
| | $4.50    [+ Add] | | $3.50    [+ Add] |            | -------------------- |
| +------------------+ +------------------+            | Subtotal:     $20.49 |
|                                                      | TOTAL:        $22.18 |
|                                                      +----------------------+
|                                                      | [ CASH ]  [ CARD ]   |
+------------------------------------------------------+----------------------+
\`\`\`
`,
    },
  ];
}
