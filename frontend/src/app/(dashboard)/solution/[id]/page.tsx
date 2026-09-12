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
  Rocket
} from 'lucide-react';
import ArtifactViewer from '@/components/ArtifactViewer';
import ExportModal from '@/components/ExportModal';
import { solutionApi } from '@/lib/api';
import { Solution, Artifact } from '@/types';

export default function SolutionViewerPage() {
  const params = useParams();
  const solutionId = params?.id as string;

  const [solution, setSolution] = useState<Solution | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);

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
        // Provide rich sample solution blueprint for demonstration
        const sampleSol: Solution = {
          id: solutionId,
          workspace_id: 'ws-demo-1',
          title: 'Omnichannel Retail POS & Inventory Platform',
          description: 'Enterprise architecture with real-time stock sync, offline POS, loyalty rewards, and role-based staff scheduling.',
          status: 'complete',
          created_at: new Date().toISOString(),
        };
        setSolution(sampleSol);
        setArtifacts(getSampleArtifacts(sampleSol.title));
      }
    }

    loadSolution();
  }, [solutionId]);

  const [showExportModal, setShowExportModal] = useState(false);

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Navigation & Header */}
      <div className="flex items-center justify-between">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            href={`/solution/${solutionId}/mvp`}
            className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-200 transition-colors"
          >
            <Rocket className="w-3.5 h-3.5 text-indigo-400" />
            <span>Build &amp; Deploy MVP</span>
          </Link>
          <Link
            href="/chat"
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-slate-300 transition-colors"
          >
            <MessageSquare className="w-3.5 h-3.5 text-indigo-400" />
            <span>Iterate with AI</span>
          </Link>
          <button
            onClick={() => setShowExportModal(true)}
            className="flex items-center gap-2 px-4 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-md shadow-indigo-500/20 transition-all hover:scale-105"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Blueprint Package</span>
          </button>
        </div>
      </div>

      {/* Solution Header Card */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-indigo-950/40 border border-white/5 shadow-xl space-y-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-medium border border-emerald-500/20 flex items-center gap-1.5">
            <CheckCircle2 className="w-3 h-3" />
            <span>Autonomous Swarm Complete</span>
          </span>
          <span className="text-slate-500">•</span>
          <span className="text-slate-400 text-[11px] flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {solution?.created_at ? new Date(solution.created_at).toLocaleDateString() : 'Today'}
          </span>
        </div>

        <h2 className="text-2xl font-extrabold text-white tracking-tight">{solution?.title}</h2>
        <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">{solution?.description}</p>
      </div>

      {/* Deep Artifact Viewer */}
      <div className="h-[750px]">
        <ArtifactViewer 
          artifacts={artifacts} 
          solutionId={solutionId}
          onArtifactUpdated={(newArt) => {
            setArtifacts([newArt, ...artifacts.filter(a => a.id !== newArt.id && a.artifact_type !== newArt.artifact_type)]);
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
    </div>
  );
}

// Helper: Rich Sample Artifacts when exploring or bootstrapping
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
      content_text: `================================================================================
HIGH-LEVEL ARCHITECTURE DESIGN (HLD)
System: ${title}
Target Scale: Enterprise / 100,000+ Daily Active Users
================================================================================

1. SYSTEM TOPOLOGY & DEPLOYMENT ARCHITECTURE
--------------------------------------------------------------------------------
Client Layer:
  - Web Single Page App (Next.js 15, React 19, Tailwind CSS)
  - Mobile POS Terminal PWA (Offline IndexedDB, Barcode Camera Engine)
  - Admin & Analytics Portal (Real-time WebSockets Dashboard)

Edge & Ingress:
  - Cloudflare Global CDN / DDoS Mitigation
  - Traefik API Gateway with JWT validation, rate limiting (Redis/token bucket)

Microservices / Subsystems (Containerized via Alpine Docker):
  - API Gateway & Authentication Service (Python FastAPI, OAuth2, RBAC)
  - Inventory & Stock Management Engine (Async event bus, Low-Stock alerts)
  - Point-of-Sale (POS) & Checkout Engine (Stripe Terminal SDK, idempotency keys)
  - Loyalty & Promotions Engine (Tier evaluation, points ledger)
  - Reporting & Data Warehouse Sync (Async pgvector, Celery/Redis workers)

Persistence Layer:
  - Primary Database: PostgreSQL 16 (Alpine Docker, Connection Pooling via PgBouncer)
  - Cache & Session Store: In-memory Redis cluster (Fallback to memory store)
  - Object Storage: S3 / MinIO for receipt PDFs and invoice documents

2. SECURITY & COMPLIANCE POSTURE
--------------------------------------------------------------------------------
  - Data-at-Rest: AES-256 encrypted volumes
  - Data-in-Transit: TLS 1.3 strict transport security
  - Authentication: JWT tokens with 24h expiration, refresh rotation
  - Authorization: Strict Role-Based Access Control (RBAC): Admin, Store Manager, Cashier, Customer
  - Audit Trail: Immutable tamper-proof append logs for all financial mutations

3. RESILIENCE & DISASTER RECOVERY
--------------------------------------------------------------------------------
  - Target SLO: 99.95% Availability (< 4.38 hours downtime/year)
  - Point-in-time recovery (PITR) with WAL archiving (RPO < 5 mins, RTO < 30 mins)
  - Offline-first cache: POS terminals continue processing sales without internet connectivity
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
      content_text: `================================================================================
LOW-LEVEL TECHNICAL DESIGN (LLD)
Component Breakdown & Dataflow Specs
================================================================================

1. INVENTORY SUBSYSTEM CLASS SPECIFICATION
--------------------------------------------------------------------------------
class StockAdjustmentService:
    def __init__(self, db_session: AsyncSession, event_bus: EventBus):
        self.db = db_session
        self.events = event_bus

    async def deduct_inventory(self, store_id: UUID, sku: str, quantity: int, transaction_id: UUID):
        async with self.db.begin():
            # Pessimistic row locking to prevent race condition double-sells
            item = await self.db.execute(
                select(InventoryItem)
                .where(InventoryItem.store_id == store_id, InventoryItem.sku == sku)
                .with_for_update()
            )
            if not item or item.available_quantity < quantity:
                raise InsufficientStockError(f"SKU {sku} has insufficient stock")
            
            item.available_quantity -= quantity
            item.reserved_quantity += quantity
            
            # Emit low stock alert if below threshold
            if item.available_quantity <= item.reorder_threshold:
                await self.events.publish("inventory.low_stock", {"sku": sku, "remaining": item.available_quantity})

2. IDEMPOTENCY & OFFLINE TRANSACTION RESOLUTION
--------------------------------------------------------------------------------
POS terminals generate UUIDv4 client_transaction_id locally.
When reconnecting:
  1. POS sends batch of transactions with client timestamps and UUIDs.
  2. Gateway checks idempotency ledger in PostgreSQL:
     INSERT INTO transactions (id, store_id, amount, status) VALUES (...) ON CONFLICT (id) DO NOTHING;
  3. If conflict: return existing transaction status without double charging.
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
      content_text: `-- ============================================================================
-- PostgreSQL 16 DDL Schema (Optimized for Alpine PostgreSQL in Docker)
-- Generated by AI Solution Builder Database & API Agent
-- ============================================================================

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

-- Inventory Stock Levels
CREATE TABLE inventory_stocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    available_qty INT NOT NULL DEFAULT 0,
    reserved_qty INT NOT NULL DEFAULT 0,
    reorder_point INT NOT NULL DEFAULT 10,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_store_product UNIQUE (store_id, product_id)
);

-- POS Sales Orders
CREATE TABLE sales_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id UUID NOT NULL REFERENCES stores(id),
    cashier_user_id UUID NOT NULL,
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    subtotal NUMERIC(10, 2) NOT NULL,
    tax_amount NUMERIC(10, 2) NOT NULL,
    discount_amount NUMERIC(10, 2) DEFAULT 0.00,
    total_amount NUMERIC(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    payment_status VARCHAR(50) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Order Items
CREATE TABLE sales_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES sales_orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    unit_price NUMERIC(10, 2) NOT NULL,
    quantity INT NOT NULL,
    line_total NUMERIC(10, 2) NOT NULL
);
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
      content_text: `openapi: 3.0.3
info:
  title: Solution Core REST API
  description: High-throughput API for Retail POS, Stock Sync & Subsystem Services
  version: 1.0.0
paths:
  /api/v1/pos/checkout:
    post:
      summary: Submit offline/online POS order with idempotency
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
                idempotency_key:
                  type: string
                  format: uuid
                store_id:
                  type: string
                  format: uuid
                payment_method:
                  type: string
                  enum: [cash, card, qr_code, split]
                items:
                  type: array
                  items:
                    type: object
                    properties:
                      product_id: { type: string, format: uuid }
                      sku: { type: string }
                      quantity: { type: integer, minimum: 1 }
                      unit_price: { type: number, format: float }
      responses:
        '201':
          description: Order processed and stock adjusted
        '409':
          description: Insufficient stock or transaction duplicate conflict

  /api/v1/inventory/stocks/{store_id}:
    get:
      summary: Query stock levels with low-stock filter
      parameters:
        - name: store_id
          in: path
          required: true
          schema: { type: string, format: uuid }
        - name: low_stock_only
          in: query
          schema: { type: boolean }
      responses:
        '200':
          description: List of items and available quantities
`,
    },
    {
      id: 'art-roadmap',
      solution_id: 'sample',
      artifact_type: 'roadmap',
      title: '12-Week Implementation & Delivery Roadmap',
      version: 1,
      created_at: new Date().toISOString(),
      content: {},
      content_text: `================================================================================
12-WEEK ENGINEERING DELIVERY ROADMAP
================================================================================

PHASE 1: FOUNDATION & DATA ARCHITECTURE (Weeks 1 - 3)
--------------------------------------------------------------------------------
- Milestone 1.1: Deploy PostgreSQL schemas, triggers, and migrations (Week 1)
- Milestone 1.2: Core FastAPI authentication, RBAC, and org multi-tenancy (Week 2)
- Milestone 1.3: Product catalog & store setup APIs (Week 3)
Deliverables: Working REST backend with automated pytest suite and DB seeds.

PHASE 2: INVENTORY ENGINE & RECONCILIATION (Weeks 4 - 6)
--------------------------------------------------------------------------------
- Milestone 2.1: Stock adjustment service with pessimistic row locks (Week 4)
- Milestone 2.2: Barcode & QR code scanning integration (Week 5)
- Milestone 2.3: Supplier restock alerts & purchase order flows (Week 6)
Deliverables: Inventory tracking with real-time stock sync.

PHASE 3: POS TERMINAL & CHECKOUT PWA (Weeks 7 - 9)
--------------------------------------------------------------------------------
- Milestone 3.1: Offline-first IndexedDB cache & quick-register UI (Week 7)
- Milestone 3.2: Stripe Terminal SDK / Card payment integration (Week 8)
- Milestone 3.3: Idempotent transaction reconciliation engine (Week 9)
Deliverables: Working POS terminal operating in both online and offline modes.

PHASE 4: HARDENING, LOAD TESTING & PRODUCTION GO-LIVE (Weeks 10 - 12)
--------------------------------------------------------------------------------
- Milestone 4.1: End-to-end security penetration audit & stress testing (Week 10)
- Milestone 4.2: CI/CD Docker image builds & staging deployment (Week 11)
- Milestone 4.3: Store pilot testing & production deployment (Week 12)
Deliverables: Production-ready enterprise release with 99.95% SLO monitoring.
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
          'Quick Category Tabs (Beverages, Fresh, Dry Goods)',
          'Product Grid with Large Tap Targets',
          'Current Cart Bill Summary (Subtotal, Tax, Total)',
          'Instant Payment Tender Buttons (Cash, Card, QR Pay)',
        ],
      },
      content_text: `+-----------------------------------------------------------------------------+
| [=] STORE #104 - REGISTER 02         Cashier: Sarah Chen   [Offline Status: OK] |
+------------------------------------------------------+----------------------+
| [Search by SKU or Scan Barcode...                 ] | CURRENT SALE (#8941) |
+------------------------------------------------------+----------------------+
| [All] [Beverages] [Bakery] [Produce] [Snacks]        | 1x Artisan Sourdough |
+------------------------------------------------------+    $4.50             |
| +------------------+ +------------------+            | 2x Cold Brew 12oz    |
| | Artisan Sourdough| | Cold Brew Coffee |            |    $7.00 ($3.50 ea)  |
| | $4.50    [+ Add] | | $3.50    [+ Add] |            | 1x Organic Honey     |
| +------------------+ +------------------+            |    $8.99             |
| +------------------+ +------------------+            | -------------------- |
| | Organic Honey    | | Avocado Bag (4pk)|            | Subtotal:     $20.49 |
| | $8.99    [+ Add] | | $5.99    [+ Add] |            | Tax (8.25%):   $1.69 |
| +------------------+ +------------------+            | TOTAL:        $22.18 |
|                                                      +----------------------+
|                                                      | [ CASH ]  [ CARD ]   |
|                                                      | [ QR ]    [ SPLIT ]  |
+------------------------------------------------------+----------------------+`,
    },
  ];
}
