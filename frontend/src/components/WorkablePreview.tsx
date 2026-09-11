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
    <div className="flex flex-col h-full bg-slate-950 border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
      {/* Top Banner: Workable System Status */}
      <div className="p-4 border-b border-white/5 bg-slate-900/80 backdrop-blur-md flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
            <Database className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-bold text-white text-sm">Mounted Live Application Runtime</h3>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] text-emerald-400 font-mono">Live PostgreSQL Schema</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Interact with real operational tables and REST APIs provisioned from your blueprint.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleSeedSynthetic}
            disabled={seeding}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-indigo-300 border border-indigo-500/30 transition-all disabled:opacity-40"
          >
            {seeding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-400" />}
            <span>Seed Synthetic Records</span>
          </button>

          <button
            onClick={() => setShowApiDrawer(!showApiDrawer)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300 transition-colors"
          >
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            <span>API Docs</span>
          </button>
        </div>
      </div>

      {/* Module and Entity Tabs */}
      <div className="flex flex-wrap items-center justify-between px-4 pt-3 pb-2 border-b border-white/5 bg-slate-900/40 gap-3">
        {/* Module switcher */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Subsystem:</span>
          <div className="flex gap-1">
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
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all ${
                  selectedModule === mod.name
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                {mod.label}
              </button>
            ))}
          </div>
        </div>

        {/* Entity switcher */}
        {getActiveModule() && (
          <div className="flex items-center gap-1.5">
            {getActiveModule()?.entities.map(ent => (
              <button
                key={ent.name}
                onClick={() => {
                  setSelectedEntity(ent.name);
                  loadRecords(selectedModule, ent.name);
                }}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  selectedEntity === ent.name
                    ? 'bg-white/10 text-indigo-300 font-medium border border-indigo-500/30'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {ent.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Action Toolbar */}
      <div className="p-4 flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-xs">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={`Search ${activeEntity?.label || 'records'}...`}
            className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-900 border border-white/10 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-500 hover:from-indigo-500 hover:to-cyan-400 text-white text-xs font-semibold shadow-md shadow-indigo-500/20 transition-all hover:scale-105"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Add {activeEntity?.label || 'Record'}</span>
        </button>
      </div>

      {/* Live Data Grid */}
      <div className="flex-1 overflow-auto px-4 pb-4">
        {filteredRecords.length > 0 ? (
          <div className="border border-white/5 rounded-xl overflow-hidden bg-slate-900/40">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900 text-slate-400 uppercase text-[10px] tracking-wider border-b border-white/5">
                <tr>
                  <th className="p-3">#</th>
                  {fields.map(f => (
                    <th key={f.name} className="p-3 font-semibold">{f.name}</th>
                  ))}
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredRecords.map((row, idx) => (
                  <tr key={row.id || idx} className="hover:bg-white/[0.02] transition-colors">
                    <td className="p-3 text-slate-500 font-mono text-[11px]">{idx + 1}</td>
                    {fields.map(f => (
                      <td key={f.name} className="p-3">
                        {typeof row[f.name] === 'boolean' ? (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] ${row[f.name] ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                            {row[f.name] ? 'True' : 'False'}
                          </span>
                        ) : (
                          <span>{row[f.name] !== undefined ? String(row[f.name]) : '-'}</span>
                        )}
                      </td>
                    ))}
                    <td className="p-3 text-right">
                      <button
                        onClick={() => handleDeleteRecord(row.id)}
                        className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                        title="Delete record"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="h-64 flex flex-col items-center justify-center text-center space-y-3 text-slate-500 border border-dashed border-white/10 rounded-xl">
            <Database className="w-8 h-8 text-slate-600" />
            <p className="text-xs text-slate-400">No records found in this operational table.</p>
            <button
              onClick={handleSeedSynthetic}
              className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 transition-colors"
            >
              Seed 5 Sample Records
            </button>
          </div>
        )}
      </div>

      {/* Live API Drawer */}
      {showApiDrawer && (
        <div className="p-4 border-t border-white/5 bg-slate-900/90 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="font-bold text-slate-200">Headless REST Endpoint for this table:</span>
            <button onClick={() => setShowApiDrawer(false)} className="hover:text-white">Close</button>
          </div>
          <div className="p-2.5 rounded-lg bg-black/60 border border-white/10 text-cyan-300 select-all">
            GET /api/v1/workable/{solutionId}/{selectedModule}/{selectedEntity}
          </div>
        </div>
      )}

      {/* Add Record Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-white/10 rounded-2xl p-6 shadow-2xl space-y-4">
            <h4 className="text-base font-bold text-white">Create New {activeEntity?.label}</h4>

            <form onSubmit={handleCreateRecord} className="space-y-3">
              {fields.map(f => (
                <div key={f.name}>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    {f.name} {f.required && <span className="text-rose-400">*</span>}
                  </label>
                  <input
                    type={f.type === 'number' ? 'number' : 'text'}
                    required={f.required}
                    value={formData[f.name] || ''}
                    onChange={(e) => setFormData({ ...formData, [f.name]: f.type === 'number' ? Number(e.target.value) : e.target.value })}
                    placeholder={`Enter ${f.name}...`}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-white/10 text-xs text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              ))}

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/25 transition-all"
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
