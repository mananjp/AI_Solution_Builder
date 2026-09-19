'use client';

import React, { useRef } from 'react';
import { motion, useScroll, useTransform, useSpring } from 'framer-motion';
import Link from 'next/link';
import { ArrowRight, Brain, Compass, Code, CheckSquare, Lightbulb, Network, Rocket, Settings, Layout, CheckCircle2, FileText, Database, ArrowDown, Files } from 'lucide-react';

// Interactive "Alive" Pipeline Card
const PipelineCard = ({ stage, index }: { stage: { step: string; title: string; desc: string; icon: React.ElementType }, index: number }) => {
  const Icon = stage.icon;
  
  return (
    <motion.div
      initial={{ y: 0 }}
      animate={{ y: [0, -10, 0] }}
      transition={{ 
        duration: 4, 
        repeat: Infinity, 
        ease: "easeInOut",
        delay: index * 0.2 // Staggered wave effect
      }}
      className="relative h-[280px] w-full rounded-2xl bg-[#111315]/80 backdrop-blur-xl border border-white/5 p-6 flex flex-col items-center justify-center shadow-lg transition-all hover:border-[var(--sutra-muted-gold)]/40 hover:bg-[#15181A]/90 hover:shadow-[0_10px_40px_rgba(176,138,74,0.15)] group z-10"
    >
      {/* Background glow on hover */}
      <div 
        className="absolute inset-0 bg-gradient-to-b from-[var(--sutra-muted-gold)]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl pointer-events-none" 
      />
      
      {/* Large background number */}
      <div 
        className="text-[var(--sutra-muted-gold)]/5 font-sanskrit text-7xl absolute top-4 right-4 pointer-events-none group-hover:text-[var(--sutra-muted-gold)]/20 transition-colors duration-500"
      >
        {stage.step}
      </div>

      <div className="relative z-10 text-center w-full flex flex-col items-center">
        {/* Pulsing ring around the icon */}
        <div className="relative w-12 h-12 mb-6 group-hover:scale-110 transition-transform duration-300">
          <motion.div 
            animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut", delay: index * 0.2 }}
            className="absolute inset-0 rounded-full border border-[var(--sutra-muted-gold)]/30 pointer-events-none"
          />
          <div className="absolute inset-0 rounded-full border border-[var(--sutra-muted-gold)]/50 flex items-center justify-center bg-[#0A0C0E] shadow-[0_0_15px_rgba(176,138,74,0.2)] group-hover:shadow-[0_0_25px_rgba(176,138,74,0.5)] transition-shadow duration-300">
            {Icon ? <Icon className="w-5 h-5 text-white group-hover:text-[var(--sutra-muted-gold)] transition-colors" /> : <span className="text-white text-xs font-bold tracking-widest">{stage.step}</span>}
          </div>
        </div>

        <h3 className="text-sm font-bold text-white mb-3 uppercase tracking-widest group-hover:text-[var(--sutra-muted-gold)] transition-colors duration-300">{stage.title}</h3>
        <p className="text-[#8E959A] text-xs leading-relaxed max-w-[180px] mx-auto font-light">
          {stage.desc}
        </p>
      </div>
    </motion.div>
  );
};

// Interactive Mock Workspace
const MockWorkspace = () => {
  return (
    <div className="w-full max-w-[1200px] mx-auto bg-[#0A0C0E]/90 backdrop-blur-2xl border border-white/10 p-1 shadow-2xl relative group overflow-hidden rounded-xl">
       {/* Window Controls */}
       <div className="h-10 bg-[#111315] rounded-t-lg border-b border-white/5 flex items-center px-4 justify-between shrink-0">
          <div className="flex gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <div className="text-[10px] uppercase tracking-widest text-[#8E959A] font-medium flex items-center gap-2">
            <span className="text-[var(--sutra-muted-gold)]">सूत्र</span> Workspace : LogisticsOS
          </div>
          <div className="flex items-center gap-2 text-[#22C55E] text-[10px] uppercase tracking-widest bg-[#22C55E]/10 px-2 py-1 rounded-full border border-[#22C55E]/20">
             <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22C55E] opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-[#22C55E]"></span>
              </span>
             Live Sync
          </div>
       </div>

       <div className="flex h-[450px] md:h-[550px]">
          {/* ZONE 1: Context Ingestion */}
          <div className="hidden md:flex w-[250px] border-r border-white/5 bg-[#0A0C0E]/50 p-4 flex-col gap-4 overflow-hidden relative shrink-0">
             <div className="text-[10px] uppercase tracking-widest text-[#8E959A] mb-2 font-bold flex items-center gap-2 shrink-0">
                <Files size={12}/> 1. Context Ingestion
             </div>

             {/* PDF Document Mock */}
             <div className="border border-white/10 bg-[#111315] rounded-md p-3 relative overflow-hidden group shrink-0 shadow-lg">
                <div className="flex items-center gap-2 mb-3">
                   <FileText size={14} className="text-red-400" />
                   <span className="text-[10px] font-bold text-white truncate">Logistics_Specs.pdf</span>
                </div>
                <div className="space-y-2 opacity-70 mb-1">
                   <div className="h-1.5 w-full bg-white/20 rounded-full" />
                   <div className="h-1.5 w-5/6 bg-white/20 rounded-full" />
                   <div className="h-1.5 w-4/6 bg-white/20 rounded-full" />
                </div>
                
                {/* Scanning Laser */}
                <motion.div 
                   animate={{ top: ['0%', '100%', '0%'] }}
                   transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                   className="absolute left-0 right-0 h-[1px] bg-red-400/50 shadow-[0_0_15px_rgba(248,113,113,0.8)] pointer-events-none z-10"
                />
             </div>

             {/* Database Schema Mock */}
             <div className="border border-white/10 bg-[#111315] rounded-md p-3 relative overflow-hidden shrink-0 shadow-lg mt-2">
                <div className="flex items-center gap-2 mb-2">
                   <Database size={14} className="text-blue-400" />
                   <span className="text-[10px] font-bold text-white">legacy_fleet_db.sql</span>
                </div>
                <div className="space-y-1.5 font-mono text-[8px] text-blue-300/60 mt-3">
                   <div>CREATE TABLE routes (</div>
                   <div className="pl-2">id UUID,</div>
                   <div className="pl-2">driver_id INT,</div>
                   <div className="pl-2">status VARCHAR</div>
                   <div>);</div>
                </div>
                {/* Glowing extraction pulse */}
                <motion.div animate={{ opacity: [0, 0.5, 0] }} transition={{ duration: 2, repeat: Infinity, delay: 1 }} className="absolute inset-0 bg-blue-500/10 pointer-events-none" />
             </div>
             
             {/* Connecting Flow */}
             <div className="flex-1 flex flex-col justify-center items-center opacity-50 relative mt-2">
                <div className="absolute top-0 bottom-0 border-l-2 border-dashed border-[var(--sutra-muted-gold)] opacity-30" />
                <motion.div animate={{ y: [0, 15, 0] }} transition={{ duration: 2, repeat: Infinity }} className="bg-[#0A0C0E] py-2 z-10">
                   <ArrowDown size={16} className="text-[var(--sutra-muted-gold)]" />
                </motion.div>
                <div className="text-[8px] text-[var(--sutra-muted-gold)] uppercase tracking-widest mt-1 text-center bg-[#0A0C0E] py-1 z-10">
                   Extracting<br/>Entities
                </div>
             </div>
          </div>

          {/* ZONE 2: Swarm Agents */}
          <div className="w-[300px] hidden lg:flex border-r border-white/5 bg-[#0A0C0E]/50 p-4 flex-col gap-4 overflow-hidden relative shrink-0">
             <div className="text-[10px] uppercase tracking-widest text-[#8E959A] mb-2 font-bold flex items-center gap-2 shrink-0">
                <Network size={12}/> 2. Swarm Intelligence
             </div>

             {/* Agent 1 */}
             <div className="border border-white/5 bg-[#111315] rounded-lg p-4 relative overflow-hidden group shrink-0">
                <div className="absolute top-0 left-0 w-1 h-full bg-[var(--sutra-muted-gold)]" />
                <div className="flex items-center justify-between mb-3">
                   <div className="flex items-center gap-2">
                      <Compass size={14} className="text-[var(--sutra-muted-gold)]" />
                      <span className="text-white text-xs font-bold">Architecture</span>
                   </div>
                   <motion.div animate={{ rotate: 360 }} transition={{ duration: 4, repeat: Infinity, ease: "linear" }}>
                     <Settings size={12} className="text-[#8E959A]" />
                   </motion.div>
                </div>
                <div className="text-[10px] text-[#8E959A] font-mono mb-2">Analyzing BPMN constraints...</div>
                {/* Scrolling data bars */}
                <div className="flex gap-1 h-8 items-end">
                   {[1,2,3,4,5,6,7,8].map((i) => (
                      <motion.div key={i} animate={{ height: ['20%', '100%', '20%'] }} transition={{ duration: 1 + i*0.1, repeat: Infinity, ease: "easeInOut" }} className="w-full bg-[var(--sutra-muted-gold)]/20 rounded-t-sm" />
                   ))}
                </div>
             </div>

             {/* Agent 2 */}
             <div className="border border-white/5 bg-[#111315] rounded-lg p-4 relative overflow-hidden shrink-0">
                <div className="absolute top-0 left-0 w-1 h-full bg-blue-500/50" />
                <div className="flex items-center justify-between mb-3">
                   <div className="flex items-center gap-2">
                      <Code size={14} className="text-blue-400" />
                      <span className="text-white text-xs font-bold">Backend</span>
                   </div>
                   <motion.div animate={{ opacity: [0.5, 1, 0.5] }} transition={{ duration: 2, repeat: Infinity }}>
                     <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
                   </motion.div>
                </div>
                <div className="text-[10px] text-blue-300/70 font-mono h-[40px] overflow-hidden relative">
                   <motion.div animate={{ y: [0, -100] }} transition={{ duration: 10, repeat: Infinity, ease: "linear" }} className="flex flex-col gap-1">
                     <span> POST /api/v1/routes</span>
                     <span> 200 OK (14ms)</span>
                     <span> Injecting postgres schemas</span>
                     <span> Validating ORM models...</span>
                     <span> Compiling router.ts</span>
                     <span> POST /api/v1/routes</span>
                     <span> 200 OK (14ms)</span>
                     <span> Injecting postgres schemas</span>
                   </motion.div>
                </div>
             </div>

             {/* Agent 3 */}
             <div className="border border-[var(--sutra-muted-gold)]/20 bg-[var(--sutra-muted-gold)]/5 rounded-lg p-4 relative overflow-hidden shadow-[0_0_15px_rgba(176,138,74,0.05)] shrink-0">
                <div className="absolute top-0 left-0 w-1 h-full bg-[#22C55E]" />
                <div className="flex items-center justify-between mb-3">
                   <div className="flex items-center gap-2">
                      <CheckSquare size={14} className="text-[#22C55E]" />
                      <span className="text-[#22C55E] text-xs font-bold">UI Synthesis</span>
                   </div>
                   <motion.div animate={{ scale: [1, 1.2, 1] }} transition={{ duration: 2, repeat: Infinity }}>
                     <CheckCircle2 size={12} className="text-[#22C55E]" />
                   </motion.div>
                </div>
                <div className="text-[10px] text-[#8E959A] font-mono leading-relaxed">
                   React components assembled. WebSocket listeners bound to state. DOM hydrated.
                </div>
             </div>
          </div>

          {/* RIGHT: Live Application Preview */}
          <div className="flex-1 bg-[#0A0C0E] relative p-6 flex flex-col overflow-hidden">
              <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(176,138,74,0.05),transparent_70%)] pointer-events-none" />
              
              <div className="flex justify-between items-center mb-6 relative z-10">
                 <div className="text-[10px] uppercase tracking-widest text-white font-bold flex items-center gap-2">
                    <Layout size={12} className="text-[var(--sutra-muted-gold)]" /> 3. Generated Application
                 </div>
                 <div className="text-[9px] text-[#8E959A] border border-white/10 px-2 py-1 rounded bg-[#111315]">
                    logistics.sutra.app
                 </div>
              </div>

              {/* Advanced Glassmorphism Dashboard */}
              <div className="flex-1 relative z-10 flex flex-col gap-4">
                 
                 {/* Glass Nav */}
                 <div className="w-full h-10 bg-white/[0.02] backdrop-blur-md border border-white/5 rounded-full flex items-center px-4 justify-between shadow-lg shrink-0">
                    <div className="flex items-center gap-2">
                       <div className="w-4 h-4 rounded-full bg-[var(--sutra-muted-gold)] flex items-center justify-center shadow-[0_0_10px_rgba(176,138,74,0.5)]">
                          <Brain size={8} className="text-black" />
                       </div>
                       <span className="font-bold text-white text-[10px] tracking-wide">Sutra_Logistics</span>
                    </div>
                    <div className="flex gap-4 text-[9px] text-[#8E959A] font-medium">
                       <span className="text-white border-b border-[var(--sutra-muted-gold)] pb-1">Overview</span>
                       <span>Agents</span>
                       <span>Endpoints</span>
                    </div>
                 </div>

                 {/* Grid Layout */}
                 <div className="flex-1 grid grid-cols-3 grid-rows-2 gap-4 min-h-0">
                    
                    {/* Big Chart Card (Spans 2 cols) */}
                    <div className="col-span-2 row-span-2 bg-gradient-to-br from-white/[0.03] to-transparent backdrop-blur-md border border-white/5 rounded-xl p-4 flex flex-col relative overflow-hidden shadow-2xl">
                       <div className="absolute top-0 right-0 w-32 h-32 bg-[var(--sutra-muted-gold)]/10 rounded-full blur-3xl pointer-events-none" />
                       <div className="text-[9px] text-[#8E959A] uppercase tracking-widest mb-1 z-10">Live Traffic</div>
                       <div className="text-2xl font-bold text-white mb-4 z-10">124.5k <span className="text-[10px] text-[#22C55E] font-normal">req/s</span></div>
                       
                       {/* Curved Line Chart */}
                       <div className="flex-1 relative w-full flex items-end">
                          <svg className="absolute inset-0 w-full h-full overflow-visible" preserveAspectRatio="none" viewBox="0 0 100 100">
                             <defs>
                                <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                                   <stop offset="0%" stopColor="var(--sutra-muted-gold)" stopOpacity="0.5" />
                                   <stop offset="100%" stopColor="var(--sutra-muted-gold)" stopOpacity="0" />
                                </linearGradient>
                             </defs>
                             {/* Area */}
                             <motion.path 
                                d="M0,100 L0,50 Q25,80 50,40 T100,20 L100,100 Z" 
                                fill="url(#lineGrad)" 
                                animate={{ d: ["M0,100 L0,50 Q25,80 50,40 T100,20 L100,100 Z", "M0,100 L0,60 Q25,40 50,60 T100,30 L100,100 Z", "M0,100 L0,50 Q25,80 50,40 T100,20 L100,100 Z"] }}
                                transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
                             />
                             {/* Line */}
                             <motion.path 
                                d="M0,50 Q25,80 50,40 T100,20" 
                                fill="none" 
                                stroke="var(--sutra-muted-gold)" 
                                strokeWidth="1.5" 
                                className="drop-shadow-[0_0_8px_var(--sutra-muted-gold)]"
                                animate={{ d: ["M0,50 Q25,80 50,40 T100,20", "M0,60 Q25,40 50,60 T100,30", "M0,50 Q25,80 50,40 T100,20"] }}
                                transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
                             />
                          </svg>
                       </div>
                    </div>

                    {/* Top Right Card: Circular Progress */}
                    <div className="col-span-1 row-span-1 bg-white/[0.02] backdrop-blur-md border border-white/5 rounded-xl p-4 flex flex-col items-center justify-center relative shadow-lg">
                       <div className="text-[8px] text-[#8E959A] uppercase tracking-widest absolute top-3 left-3">System Load</div>
                       <div className="relative w-16 h-16 mt-4">
                          <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
                             <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="3" />
                             <motion.path 
                                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" 
                                fill="none" 
                                stroke="#22C55E" 
                                strokeWidth="3" 
                                strokeDasharray="100 100"
                                animate={{ strokeDashoffset: [100, 30, 60, 30] }}
                                transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
                             />
                          </svg>
                          <div className="absolute inset-0 flex items-center justify-center text-white text-xs font-bold">
                             <motion.span animate={{ opacity: [0.7, 1, 0.7] }} transition={{ duration: 2, repeat: Infinity }}>72%</motion.span>
                          </div>
                       </div>
                    </div>

                    {/* Bottom Right Card: Activity Feed */}
                    <div className="col-span-1 row-span-1 bg-white/[0.02] backdrop-blur-md border border-white/5 rounded-xl p-3 flex flex-col overflow-hidden shadow-lg">
                       <div className="text-[8px] text-[#8E959A] uppercase tracking-widest mb-3">Live Logs</div>
                       <div className="flex-1 overflow-hidden relative">
                          <motion.div 
                             animate={{ y: [0, -40] }} 
                             transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
                             className="flex flex-col gap-2.5"
                          >
                             {[...Array(6)].map((_, i) => (
                                <div key={i} className="flex items-center gap-2">
                                   <div className={`w-1.5 h-1.5 rounded-full shadow-[0_0_5px_currentColor] ${i % 2 === 0 ? 'bg-[#22C55E] text-[#22C55E]' : 'bg-[var(--sutra-muted-gold)] text-[var(--sutra-muted-gold)]'}`} />
                                   <div className="h-1.5 bg-white/10 rounded-full flex-1" />
                                </div>
                             ))}
                          </motion.div>
                          <div className="absolute inset-x-0 bottom-0 h-8 bg-gradient-to-t from-[#0A0C0E] to-transparent pointer-events-none" />
                       </div>
                    </div>

                 </div>

                 {/* Deployment Overlay - Same as before */}
                 <motion.div 
                    animate={{ opacity: [0, 0, 1, 1, 0] }}
                    transition={{ duration: 10, repeat: Infinity, times: [0, 0.75, 0.8, 0.95, 1] }}
                    className="absolute inset-0 bg-[#0A0C0E]/90 backdrop-blur-md flex flex-col items-center justify-center rounded-xl border border-[#22C55E]/30 z-30"
                 >
                    <Rocket className="w-12 h-12 text-[#22C55E] mb-4 drop-shadow-[0_0_15px_rgba(34,197,94,0.5)]" />
                    <span className="text-[#22C55E] text-sm uppercase tracking-widest font-bold mb-2">Successfully Deployed</span>
                    <span className="text-[#8E959A] text-xs font-sans">Production system is live.</span>
                    <div className="mt-6 px-4 py-2 bg-[#22C55E]/10 border border-[#22C55E]/30 text-[#22C55E] rounded-md text-[10px] font-mono tracking-wide shadow-[0_0_15px_rgba(34,197,94,0.1)]">
                      https://logistics.sutra.app
                    </div>
                 </motion.div>
              </div>
          </div>

       </div>
    </div>
  );
};

export default function LandingPage() {
  const pageRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: pageRef,
    offset: ['start start', 'end end']
  });

  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 100,
    damping: 30,
    restDelta: 0.001
  });

  // The scroll effect draws the logo from 5% to 100% as you scroll down the page
  const pathLength = useTransform(smoothProgress, [0, 1], [0.05, 1]);

  return (
    <div ref={pageRef} className="relative bg-[#0A0C0E] text-[#FAF8F3] min-h-screen selection:bg-[var(--sutra-muted-gold)] selection:text-[#0A0C0E] font-sans overflow-x-hidden">
      
      {/* GLOBAL 3D BACKGROUND SCROLL EFFECT (THE LOGO) */}
      <div className="fixed inset-0 w-full h-full flex items-center justify-center pointer-events-none z-0 perspective-[1000px]">
        {/* Ambient Glow */}
        <div className="absolute inset-0 bg-radial-gradient from-[#B08A4A]/5 via-[#0A0C0E]/90 to-[#0A0C0E]" />
        
        <motion.div 
          initial={{ rotateX: 20, rotateY: -15, scale: 0.85 }}
          animate={{ 
            rotateX: [15, 25, 15], 
            rotateY: [-10, 10, -10],
            scale: [0.85, 0.9, 0.85]
          }}
          transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
          className="w-[800px] h-[800px] md:w-[1200px] md:h-[1200px] opacity-30 blur-[2px] mix-blend-screen"
        >
          <svg viewBox="0 0 1000 1000" fill="none" className="w-full h-full overflow-visible">
            {/* Vertical Line with Diamond Ends */}
            <motion.path 
              d="M 500 50 L 515 80 L 500 110 L 485 80 Z" 
              fill="none" 
              stroke="#B08A4A" 
              strokeWidth="4" 
              style={{ pathLength }}
            />
            <motion.path 
              d="M 500 110 L 500 890" 
              stroke="#B08A4A" 
              strokeWidth="4" 
              strokeLinecap="round" 
              style={{ pathLength }}
            />
            <motion.path 
              d="M 500 890 L 515 920 L 500 950 L 485 920 Z" 
              fill="none" 
              stroke="#B08A4A" 
              strokeWidth="4" 
              style={{ pathLength }}
            />

            {/* The Elliptical Orbit Ring */}
            <motion.ellipse 
              cx="500" 
              cy="500" 
              rx="400" 
              ry="120" 
              transform="rotate(-20 500 500)" 
              stroke="#FAF8F3" 
              strokeWidth="2" 
              strokeOpacity="0.4" 
              style={{ pathLength }}
            />
            
            {/* Orbiting dot */}
            <motion.circle 
              cx="900" 
              cy="500" 
              r="12" 
              transform="rotate(-20 500 500)" 
              fill="none" 
              stroke="#FAF8F3" 
              strokeWidth="3" 
              style={{ pathLength }}
            />

            {/* The Bold "S" Shape */}
            <motion.path 
              d="M 700 250 C 700 50, 300 50, 300 250 C 300 450, 700 550, 700 750 C 700 950, 300 950, 300 750" 
              stroke="#FAF8F3" 
              strokeWidth="32" 
              strokeLinecap="round" 
              style={{ pathLength }}
            />
          </svg>
        </motion.div>
      </div>

      {/* FOREGROUND CONTENT */}
      <div className="relative z-10">
        {/* HEADER */}
        <header className="absolute top-0 left-0 w-full h-20 flex items-center justify-between px-8 z-50">
          <div className="flex items-center">
            <span className="text-[var(--sutra-muted-gold)] font-sanskrit font-bold text-4xl leading-none drop-shadow-sm">सूत्र</span>
          </div>
          <div className="flex items-center gap-6">
            <Link href="/login" className="text-[12px] uppercase tracking-widest text-[#8E959A] hover:text-white transition-colors">
              Sign in
            </Link>
            <Link href="/dashboard" className="btn btn-primary bg-[var(--sutra-muted-gold)] text-[#0A0C0E] hover:bg-[#C29B5A] border-none text-[11px] uppercase tracking-widest px-5 py-2">
              Workspace <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Link>
          </div>
        </header>

        {/* HERO SECTION */}
        <section className="min-h-[95vh] w-full flex flex-col items-center justify-center pt-20">
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 1, delay: 0.2 }}
            className="flex flex-col items-center text-center px-4 max-w-4xl mx-auto"
          >
            <div className="inline-flex items-center gap-3 text-[10px] md:text-xs uppercase tracking-[0.3em] text-[var(--sutra-muted-gold)] font-bold mb-8">
              <span className="w-8 h-[1px] bg-[var(--sutra-muted-gold)] opacity-50" />
              Ancient precision. Modern intelligence.
              <span className="w-8 h-[1px] bg-[var(--sutra-muted-gold)] opacity-50" />
            </div>

            <h1 className="text-5xl md:text-7xl lg:text-[90px] font-serif text-[#FAF8F3] tracking-tight leading-[0.9] mb-8">
              Structure your <br />
              <span className="italic text-transparent bg-clip-text bg-gradient-to-r from-[var(--sutra-muted-gold)] to-[#FAF8F3]">
                intelligence.
              </span>
            </h1>
            
            <p className="text-[#8E959A] text-lg md:text-xl font-light leading-relaxed max-w-2xl text-balance mb-12">
              The autonomous pipeline that dissects business requirements, performs rigorous architectural reasoning, and synthesizes production-ready software systems in minutes.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4">
              <Link href="/chat" className="btn btn-primary bg-[var(--sutra-muted-gold)] text-[#0A0C0E] hover:bg-[#C29B5A] border-none text-sm uppercase tracking-widest px-8 py-4 shadow-[0_0_40px_rgba(176,138,74,0.3)] transition-shadow hover:shadow-[0_0_60px_rgba(176,138,74,0.5)]">
                Build with SUTRA 
              </Link>
              <Link href="/dashboard" className="btn btn-ghost text-sm uppercase tracking-widest px-8 py-4 border border-white/10 hover:border-[var(--sutra-muted-gold)] hover:bg-white/5 transition-colors text-white backdrop-blur-md">
                Explore Workspaces
              </Link>
            </div>
          </motion.div>

          {/* Scroll Indicator */}
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 2, duration: 1 }}
            className="absolute bottom-12 left-0 w-full flex flex-col items-center justify-center text-center z-20 pointer-events-none"
          >
            <div className="w-[1px] h-16 bg-gradient-to-b from-[#8E959A] to-transparent overflow-hidden relative">
              <motion.div 
                animate={{ y: [0, 64] }}
                transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }}
                className="w-full h-1/2 bg-[var(--sutra-muted-gold)]"
              />
            </div>
          </motion.div>
        </section>

        {/* REST OF THE PAGE */}
        <div className="border-t border-white/5">
          <main className="max-w-[1400px] mx-auto px-6 md:px-12">
            
            {/* THE SUTRA PIPELINE */}
            <section className="py-32 relative border-b border-white/5">
              <div className="mb-20 text-center">
                <h2 className="text-3xl md:text-4xl font-serif text-white tracking-tight mb-4">The Architectural Pipeline</h2>
                <p className="text-[#8E959A] uppercase tracking-widest text-xs font-semibold">From raw intent to tangible software.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-5 gap-6 relative perspective-[1000px]">
                {/* Connecting Laser Pulse (Desktop) */}
                <div className="hidden md:block absolute top-[140px] left-12 right-12 h-[2px] bg-[#111315] z-0 overflow-hidden rounded-full border border-white/5">
                  <motion.div 
                    animate={{ x: ['-100%', '500%'] }} 
                    transition={{ duration: 4, repeat: Infinity, ease: 'linear' }} 
                    className="w-1/4 h-full bg-gradient-to-r from-transparent via-[var(--sutra-muted-gold)] to-transparent shadow-[0_0_15px_var(--sutra-muted-gold)]" 
                  />
                </div>
                
                {[
                  { step: '01', title: 'Idea', desc: 'Raw business requirement ingestion and scope extraction.', icon: Lightbulb },
                  { step: '02', title: 'Understand', desc: 'Semantic breakdown of constraints and user flows.', icon: Brain },
                  { step: '03', title: 'Reason', desc: 'Multi-agent architectural negotiation and schema design.', icon: Network },
                  { step: '04', title: 'Build', desc: 'Synthesis of robust APIs and user interface components.', icon: Code },
                  { step: '05', title: 'Deploy', desc: 'Instantly accessible, production-ready operational system.', icon: Rocket }
                ].map((stage, idx) => (
                  <PipelineCard key={idx} stage={stage} index={idx} />
                ))}
              </div>
            </section>

            {/* PRODUCT PREVIEW: INTERACTIVE MOCK WORKSPACE */}
            <section className="py-32">
              <div className="mb-16 text-center">
                <h2 className="text-3xl md:text-4xl font-serif text-white tracking-tight mb-4">A Workspace for Structured Thought</h2>
                <p className="text-[#8E959A] text-sm md:text-base font-light max-w-xl mx-auto">Inspect artifacts, review AI reasoning, and interact with live prototypes in a unified, cinematic environment.</p>
              </div>

              <MockWorkspace />
            </section>

            {/* FEATURE CAPABILITIES */}
            <section className="py-32 relative">
              
              <div className="relative z-10 grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="col-span-1 md:col-span-2 mb-16 text-center">
                  <h2 className="text-4xl md:text-5xl font-serif text-white tracking-tight mb-4">Core Engine Capabilities</h2>
                  <p className="text-[#8E959A] uppercase tracking-widest text-xs font-semibold">Intelligence at every layer.</p>
                </div>
                
                {[
                  { title: 'Semantic Ingestion', desc: 'Transform ambiguous business problems into perfectly structured requirements, mapped against enterprise ontology templates.', icon: Brain, 
                    visual: (
                      <div className="absolute inset-0 flex items-center justify-center opacity-10 pointer-events-none overflow-hidden">
                        {[1,2,3,4,5].map((i) => (
                           <motion.div key={i} animate={{ y: [-100, 300], opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 4, delay: i * 0.5, ease: 'linear' }} className="absolute w-[1px] h-48 bg-gradient-to-b from-transparent via-[var(--sutra-muted-gold)] to-transparent" style={{ left: `${15 + i * 15}%` }} />
                        ))}
                      </div>
                    )
                  },
                  { title: 'Multi-Agent Reasoning', desc: 'Break complex problems into actionable components. The swarm negotiates architecture, database schemas, and UX flows simultaneously.', icon: Compass,
                    visual: (
                      <div className="absolute inset-0 flex items-center justify-center opacity-10 pointer-events-none">
                         <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 25, ease: "linear" }} className="w-72 h-72 rounded-full border border-dashed border-[var(--sutra-muted-gold)]" />
                         <motion.div animate={{ rotate: -360 }} transition={{ repeat: Infinity, duration: 15, ease: "linear" }} className="absolute w-48 h-48 rounded-full border border-[var(--sutra-muted-gold)]" />
                         <div className="absolute w-2 h-2 rounded-full bg-[var(--sutra-muted-gold)] shadow-[0_0_20px_var(--sutra-muted-gold)] animate-ping" />
                      </div>
                    )
                  },
                  { title: 'Deterministic Synthesis', desc: 'Generate a structured solution from the reasoning process. Deploy fully operational Next.js and FastAPI environments instantly.', icon: Code,
                    visual: (
                      <div className="absolute right-0 bottom-0 p-8 flex flex-col gap-3 opacity-10 pointer-events-none w-full items-end">
                         {[60, 100, 40, 80].map((w, i) => (
                            <motion.div key={i} animate={{ width: ['0%', `${w}%`, `${w}%`, '0%'] }} transition={{ repeat: Infinity, duration: 6, times: [0, 0.4, 0.8, 1], delay: i * 0.3 }} className="h-1.5 bg-[var(--sutra-muted-gold)] rounded-l-full" style={{ width: `${w}%` }} />
                         ))}
                      </div>
                    )
                  },
                  { title: 'Tangible Inspection', desc: 'Explore generated artifacts, intermediate reasoning results, OpenAPI specs, and high-level designs in an interactive workspace.', icon: CheckSquare,
                    visual: (
                      <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'linear-gradient(#B08A4A33 1px, transparent 1px), linear-gradient(90deg, #B08A4A33 1px, transparent 1px)', backgroundSize: '30px 30px' }}>
                         <motion.div animate={{ top: ['-50%', '150%'] }} transition={{ duration: 6, repeat: Infinity, ease: 'linear' }} className="absolute left-0 right-0 h-48 bg-gradient-to-b from-transparent to-[var(--sutra-muted-gold)]" />
                      </div>
                    )
                  }
                ].map((feature, i) => (
                  <div key={i} className="p-10 group border border-white/10 bg-gradient-to-b from-[#111315]/90 to-[#0A0C0E] backdrop-blur-xl hover:border-[var(--sutra-muted-gold)]/40 transition-all duration-500 relative overflow-hidden rounded-2xl shadow-2xl hover:-translate-y-1">
                    
                    {/* Animated Visuals */}
                    {feature.visual}

                    {/* Ambient Glow */}
                    <div className="absolute -right-20 -top-20 w-64 h-64 bg-[var(--sutra-muted-gold)] opacity-0 group-hover:opacity-[0.08] rounded-full blur-3xl transition-opacity duration-700 pointer-events-none" />
                    
                    <div className="relative z-10 flex flex-col h-full">
                       <div className="w-14 h-14 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center mb-8 group-hover:scale-110 group-hover:bg-[var(--sutra-muted-gold)]/10 group-hover:border-[var(--sutra-muted-gold)]/30 transition-all duration-500 shadow-lg">
                          <feature.icon className="w-6 h-6 text-[#8E959A] group-hover:text-[var(--sutra-muted-gold)] transition-colors duration-500" />
                       </div>
                       <h3 className="text-2xl font-serif text-white mb-4 tracking-wide group-hover:text-[var(--sutra-muted-gold)] transition-colors duration-500">{feature.title}</h3>
                       <p className="text-[15px] text-[#8E959A] leading-relaxed font-light group-hover:text-[#A0A6AB] transition-colors duration-500">{feature.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

          </main>

          <footer className="border-t border-white/5 py-12 px-8 max-w-[1400px] mx-auto flex flex-col md:flex-row items-center justify-between text-xs text-[#5A6066]">
            <div className="flex items-center gap-4">
              <span className="font-sanskrit text-xl text-[var(--sutra-muted-gold)]">सूत्र</span>
              <p className="uppercase tracking-widest font-bold">Sutra OS</p>
            </div>
            <div className="flex items-center gap-8 mt-6 md:mt-0 uppercase tracking-widest font-semibold">
              <Link href="/dashboard" className="hover:text-white transition-colors">Workspace</Link>
              <Link href="/chat" className="hover:text-white transition-colors">Builder</Link>
              <Link href="/login" className="hover:text-white transition-colors">Account</Link>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}
