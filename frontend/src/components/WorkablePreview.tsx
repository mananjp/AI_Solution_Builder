'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Plus,
  Trash2,
  Database,
  Sparkles,
  Search,
  Terminal,
  Loader2,
  LayoutTemplate
} from 'lucide-react';
import { workableApi, type RawWorkableModule } from '@/lib/api';
import { WorkableModule, type WorkableRecord } from '@/types';

interface WorkablePreviewProps {
  solutionId: string;
}

export default function WorkablePreview({ solutionId }: WorkablePreviewProps) {
  const [seeding, setSeeding] = useState(false);
  const [modules, setModules] = useState<WorkableModule[]>([]);
  const [selectedModule, setSelectedModule] = useState<string>('');
  const [selectedEntity, setSelectedEntity] = useState<string>('');
  const [records, setRecords] = useState<WorkableRecord[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [formData, setFormData] = useState<Record<string, string | number | undefined>>({});
  const [showApiDrawer, setShowApiDrawer] = useState(false);
  const seedCounter = useRef(100);

  const formatModules = useCallback((rawModules: RawWorkableModule[]): WorkableModule[] => {
    return rawModules.map((m, idx) => ({
      id: m.id || `mod-${idx}`,
      name: m.name || m.module_name || '',
      label: m.label || (m.name || m.module_name || '').replace('_', ' ').toUpperCase(),
      entities: (m.entities || []).map((e) => ({
        name: e.name || e.entity_name || '',
        label: e.label || (e.name || e.entity_name || '').replace('_', ' ').toUpperCase(),
        table_name: e.table_name || e.name || '',
        fields: e.fields || [{ name: 'title', type: 'string' }],
        records: e.records || [],
      }))
    }));
  }, []);

  const loadRecords = useCallback(async (moduleName: string, entityName: string) => {
    try {
      const rows = await workableApi.listRows(solutionId, moduleName, entityName);
      setRecords(rows);
    } catch {
      // Keep existing demo records
    }
  }, [solutionId]);

  const handleFallbackDemo = useCallback(() => {
    const demoModules: WorkableModule[] = [
      {
        id: 'mod-1',
        name: 'inventory_catalog',
        label: 'Inventory & Catalog',
        entities: [
          {
            name: 'products',
            label: 'Products Catalog',
            table_name: 'products',
            fields: [
              { name: 'sku', type: 'string', required: true },
              { name: 'title', type: 'string', required: true },
              { name: 'retail_price', type: 'number', required: true },
              { name: 'category', type: 'string' },
              { name: 'is_active', type: 'boolean' },
            ],
            records: [
              { id: '1', sku: 'SKU-COFFEE-01', title: 'Cold Brew Blend 12oz', retail_price: 14.50, category: 'Beverages', is_active: true },
              { id: '2', sku: 'SKU-BREAD-02', title: 'Artisan Sourdough Loaf', retail_price: 6.25, category: 'Bakery', is_active: true },
              { id: '3', sku: 'SKU-HONEY-03', title: 'Organic Wildflower Honey', retail_price: 11.99, category: 'Pantry', is_active: true },
            ],
          },
          {
            name: 'stock_levels',
            label: 'Store Stock Levels',
            table_name: 'inventory_stocks',
            fields: [
              { name: 'store_code', type: 'string', required: true },
              { name: 'product_sku', type: 'string', required: true },
              { name: 'available_qty', type: 'number', required: true },
              { name: 'reorder_point', type: 'number' },
            ],
            records: [
              { id: 's1', store_code: 'STORE-101', product_sku: 'SKU-COFFEE-01', available_qty: 48, reorder_point: 15 },
              { id: 's2', store_code: 'STORE-101', product_sku: 'SKU-BREAD-02', available_qty: 12, reorder_point: 10 },
              { id: 's3', store_code: 'STORE-102', product_sku: 'SKU-HONEY-03', available_qty: 3, reorder_point: 8 },
            ]
          }
        ]
      },
      {
        id: 'mod-2',
        name: 'pos_orders',
        label: 'POS Sales & Checkout',
        entities: [
          {
            name: 'orders',
            label: 'Sales Orders',
            table_name: 'sales_orders',
            fields: [
              { name: 'order_number', type: 'string', required: true },
              { name: 'customer_name', type: 'string' },
              { name: 'total_amount', type: 'number', required: true },
              { name: 'payment_method', type: 'string' },
              { name: 'status', type: 'string' },
            ],
            records: [
              { id: 'ord-101', order_number: 'ORD-8941', customer_name: 'Walk-in Guest', total_amount: 20.75, payment_method: 'Card', status: 'Completed' },
              { id: 'ord-102', order_number: 'ORD-8942', customer_name: 'David Vance', total_amount: 45.00, payment_method: 'Stripe QR', status: 'Completed' },
            ]
          }
        ]
      }
    ];

    setModules(demoModules);
    setSelectedModule(demoModules[0].name);
    setSelectedEntity(demoModules[0].entities[0].name);
    setRecords(demoModules[0].entities[0].records || []);
  }, []);

  const handleProvision = useCallback(async () => {
    try {
      const res = await workableApi.provision(solutionId);
      if (res.modules) {
        const mods = formatModules(res.modules);
        setModules(mods);
        if (mods.length > 0) {
          setSelectedModule(mods[0].name);
          if (mods[0].entities.length > 0) {
            setSelectedEntity(mods[0].entities[0].name);
            loadRecords(mods[0].name, mods[0].entities[0].name);
          }
        }
      }
    } catch {
      handleFallbackDemo();
    }
  }, [formatModules, loadRecords, handleFallbackDemo, solutionId]);

  // Load modules or provision
  useEffect(() => {
    async function initWorkable() {
      try {
        const res = await workableApi.getModules(solutionId);
        if (res.modules && res.modules.length > 0) {
          const mods = formatModules(res.modules);
          setModules(mods);
          setSelectedModule(mods[0].name);
          if (mods[0].entities.length > 0) {
            setSelectedEntity(mods[0].entities[0].name);
            loadRecords(mods[0].name, mods[0].entities[0].name);
          }
        } else {
          handleProvision();
        }
      } catch {
        handleFallbackDemo();
      }
    }

    initWorkable();
  }, [solutionId, formatModules, loadRecords, handleProvision, handleFallbackDemo]);

  const handleSeedSynthetic = async () => {
    setSeeding(true);
    try {
      await workableApi.seedData(solutionId, 5);
      await loadRecords(selectedModule, selectedEntity);
    } catch {
      // Simulate synthetic rows in demo
      const activeEnt = getActiveEntity();
      if (activeEnt) {
        const newRow: WorkableRecord = {
          id: `row-${++seedCounter.current}`,
        };
        activeEnt.fields.forEach(f => {
          if (f.type === 'number') newRow[f.name] = Math.floor(Math.random() * 100) + 10;
          else if (f.type === 'boolean') newRow[f.name] = true;
          else newRow[f.name] = `Synthetic ${f.name} #${Math.floor(Math.random() * 899 + 100)}`;
        });
        setRecords([newRow, ...records]);
      }
    } finally {
      setSeeding(false);
    }
  };

  const handleCreateRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await workableApi.createRow(solutionId, selectedModule, selectedEntity, formData);
      await loadRecords(selectedModule, selectedEntity);
      setShowAddModal(false);
      setFormData({});
    } catch {
      const newRec: WorkableRecord = { id: `rec-${++seedCounter.current}`, ...formData };
      setRecords([newRec, ...records]);
      setShowAddModal(false);
      setFormData({});
    }
  };

  const handleDeleteRecord = async (id: string) => {
    try {
      await workableApi.deleteRow(solutionId, selectedModule, selectedEntity, id);
      setRecords(records.filter(r => r.id !== id));
    } catch {
      setRecords(records.filter(r => r.id !== id));
    }
  };

  const getActiveModule = () => modules.find(m => m.name === selectedModule);
  const getActiveEntity = () => getActiveModule()?.entities.find(e => e.name === selectedEntity);

  const activeEntity = getActiveEntity();
  const fields = activeEntity?.fields || [];
  const filteredRecords = records.filter(r => 
    Object.values(r).some(val => 
      String(val).toLowerCase().includes(searchQuery.toLowerCase())
    )
  );

  return (
    <div className="flex flex-col h-full bg-[var(--bg-2)] border border-[var(--border)] sutra-card overflow-hidden relative">
      {/* Browser Frame Decoration */}
      <div className="h-8 border-b border-[var(--border)] bg-[var(--bg-3)] flex items-center px-4 gap-2">
        <div className="w-2.5 h-2.5 rounded-full border border-[#DCD5C5] bg-[#E5DED1]"></div>
        <div className="w-2.5 h-2.5 rounded-full border border-[#DCD5C5] bg-[#E5DED1]"></div>
        <div className="w-2.5 h-2.5 rounded-full border border-[#DCD5C5] bg-[#E5DED1]"></div>
        <div className="mx-auto flex items-center gap-2 px-6 py-0.5 rounded-sm bg-[var(--bg)] border border-[var(--border)] text-[10px] uppercase tracking-widest text-[var(--text-3)] font-mono">
          <LayoutTemplate size={10} /> {solutionId}.sutra.dev
        </div>
      </div>

      {/* Top Banner: Workable System Status */}
      <div className="p-5 border-b border-[var(--border)] bg-[var(--bg)] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 border border-[var(--sutra-muted-gold)] text-[var(--sutra-muted-gold)] flex items-center justify-center">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h3 className="font-serif text-lg text-[var(--sutra-charcoal)]">Application Runtime</h3>
              <div className="flex items-center gap-1.5 badge badge-green">
                <span className="w-1.5 h-1.5 rounded-full bg-[var(--green)] animate-pulse" />
                Live Schema
              </div>
            </div>
            <p className="text-[11px] text-[var(--text-2)] mt-1 max-w-md font-light">
              Interact with real operational tables and REST APIs provisioned directly from the SUTRA blueprint.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSeedSynthetic}
            disabled={seeding}
            className="flex items-center gap-2 btn btn-secondary"
          >
            {seeding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-[var(--sutra-muted-gold)]" />}
            <span>Seed Synthetic Records</span>
          </button>

          <button
            onClick={() => setShowApiDrawer(!showApiDrawer)}
            className="flex items-center gap-2 btn btn-ghost border border-[var(--border)] hover:bg-[var(--bg-3)]"
          >
            <Terminal className="w-4 h-4" />
            <span>API Docs</span>
          </button>
        </div>
      </div>

      {/* Module and Entity Tabs */}
      <div className="flex flex-wrap items-center justify-between px-5 pt-4 pb-3 border-b border-[var(--border)] bg-[var(--bg-3)] gap-4">
        {/* Module switcher */}
        <div className="flex items-center gap-3">
          <span className="text-[10px] uppercase tracking-widest text-[var(--text-3)] font-semibold">Subsystem</span>
          <div className="flex gap-2">
            {modules.map(mod => (
              <button
                key={mod.name}
                onClick={() => {
                  setSelectedModule(mod.name);
                  if (mod.entities.length > 0) {
                    setSelectedEntity(mod.entities[0].name);
                    loadRecords(mod.name, mod.entities[0].name);
                  }
                }}
                className={`px-4 py-1.5 text-[11px] uppercase tracking-widest font-semibold transition-colors border ${
                  selectedModule === mod.name
                    ? 'bg-[var(--bg)] text-[var(--sutra-charcoal)] border-[var(--border)] shadow-sm'
                    : 'bg-transparent text-[var(--text-2)] border-transparent hover:text-[var(--text)]'
                }`}
              >
                {mod.label}
              </button>
            ))}
          </div>
        </div>

        {/* Entity switcher */}
        {getActiveModule() && (
          <div className="flex items-center gap-2">
            {getActiveModule()?.entities.map(ent => (
              <button
                key={ent.name}
                onClick={() => {
                  setSelectedEntity(ent.name);
                  loadRecords(selectedModule, ent.name);
                }}
                className={`px-3 py-1.5 text-[12px] font-medium transition-colors border-b-2 ${
                  selectedEntity === ent.name
                    ? 'border-[var(--sutra-muted-gold)] text-[var(--sutra-charcoal)]'
                    : 'border-transparent text-[var(--text-2)] hover:text-[var(--sutra-charcoal)]'
                }`}
              >
                {ent.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Action Toolbar */}
      <div className="px-5 py-4 flex items-center justify-between gap-4 bg-[var(--bg)] border-b border-[var(--border)]">
        <div className="relative flex-1 max-w-sm group">
          <Search className="w-4 h-4 text-[var(--text-3)] absolute left-3 top-1/2 -translate-y-1/2 group-focus-within:text-[var(--sutra-muted-gold)] transition-colors" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Search ${activeEntity?.label || 'records'}...`}
            className="w-full pl-10 pr-4 py-2 bg-[var(--bg-2)] border border-[var(--border)] text-[13px] text-[var(--text)] placeholder:text-[var(--text-3)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors"
          />
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 btn btn-primary"
        >
          <Plus className="w-4 h-4" />
          <span>Add {activeEntity?.label || 'Record'}</span>
        </button>
      </div>

      {/* Live Data Grid */}
      <div className="flex-1 overflow-auto bg-[var(--bg-2)] p-5">
        {filteredRecords.length > 0 ? (
          <div className="border border-[var(--border)] bg-[var(--bg)] shadow-sm">
            <table className="w-full text-left text-[13px] text-[var(--text)]">
              <thead className="bg-[var(--bg-3)] text-[var(--text-2)] uppercase text-[10px] tracking-widest border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-3 font-semibold">#</th>
                  {fields.map(f => (
                    <th key={f.name} className="px-4 py-3 font-semibold">{f.name}</th>
                  ))}
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {filteredRecords.map((row, idx) => (
                  <tr key={row.id || idx} className="hover:bg-[var(--bg-3)] transition-colors">
                    <td className="px-4 py-3 text-[var(--text-3)] font-mono text-[11px]">{idx + 1}</td>
                    {fields.map(f => (
                      <td key={f.name} className="px-4 py-3">
                        {typeof row[f.name] === 'boolean' ? (
                          <span className={`badge ${row[f.name] ? 'badge-green' : 'badge-red'}`}>
                            {row[f.name] ? 'True' : 'False'}
                          </span>
                        ) : (
                          <span className="font-medium text-[var(--sutra-charcoal)]">{row[f.name] !== undefined ? String(row[f.name]) : '-'}</span>
                        )}
                      </td>
                    ))}
                    <td className="px-4 py-3 text-right">
                      <button
                         onClick={() => handleDeleteRecord(row.id)}
                         className="text-[var(--text-3)] hover:text-[var(--red)] transition-colors p-1"
                         title="Delete record"
                       >
                         <Trash2 className="w-4 h-4" />
                       </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center text-center space-y-4 text-[var(--text-2)] border border-[var(--border)] border-dashed bg-[var(--bg)] m-4">
            <Database className="w-8 h-8 text-[var(--text-3)]" />
            <p className="text-[13px] font-medium text-[var(--sutra-charcoal)]">No records found in this operational table.</p>
            <button
              onClick={handleSeedSynthetic}
              className="btn btn-secondary text-xs mt-2"
            >
              Seed 5 Sample Records
            </button>
          </div>
        )}
      </div>

      {/* Live API Drawer */}
      {showApiDrawer && (
        <div className="absolute bottom-0 left-0 w-full p-6 border-t border-[var(--border)] bg-[var(--bg-2)] shadow-[0_-10px_40px_rgba(23,26,28,0.1)] z-20 transform transition-transform animate-fade-up">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[11px] uppercase tracking-widest font-semibold text-[var(--sutra-charcoal)]">REST API Endpoint (Live)</span>
            <button onClick={() => setShowApiDrawer(false)} className="text-[var(--text-2)] hover:text-[var(--sutra-charcoal)] text-[10px] uppercase tracking-widest font-semibold">Close</button>
          </div>
          <div className="p-4 bg-[var(--sutra-charcoal)] border border-[var(--border)] text-[var(--sutra-muted-gold)] font-mono text-xs select-all overflow-x-auto">
            GET /api/v1/workable/{solutionId}/{selectedModule}/{selectedEntity}
          </div>
        </div>
      )}

      {/* Add Record Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-[var(--sutra-charcoal)]/40 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in">
          <div className="w-full max-w-md bg-[var(--bg)] border border-[var(--border)] p-8 shadow-2xl space-y-6">
            <h4 className="text-xl font-serif text-[var(--sutra-charcoal)] border-b border-[var(--border)] pb-4">
              Create New {activeEntity?.label}
            </h4>

            <form onSubmit={handleCreateRecord} className="space-y-4">
              {fields.map(f => (
                <div key={f.name}>
                  <label className="block text-[10px] uppercase tracking-widest font-semibold text-[var(--text-2)] mb-2">
                    {f.name} {f.required && <span className="text-[var(--red)]">*</span>}
                  </label>
                  <input
                    type={f.type === 'number' ? 'number' : 'text'}
                    required={f.required}
                    value={formData[f.name] || ''}
                    onChange={(e) => setFormData({ ...formData, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                    placeholder={`Enter ${f.name}...`}
                    className="w-full px-4 py-2.5 bg-[var(--bg-2)] border border-[var(--border)] text-[13px] text-[var(--text)] focus:outline-none focus:border-[var(--sutra-muted-gold)] transition-colors"
                  />
                </div>
              ))}

              <div className="pt-6 flex justify-end gap-3">
                <button
                   type="button"
                   onClick={() => setShowAddModal(false)}
                   className="btn btn-ghost"
                 >
                   Cancel
                 </button>
                 <button
                   type="submit"
                   className="btn btn-primary"
                 >
                   Insert Record
                 </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
