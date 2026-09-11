'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import Navbar from '@/components/Navbar';

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-[#070a13] text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Fixed Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col">
        <Navbar />
        <main className="flex-1 ml-64 p-8 relative overflow-y-auto">
          {/* Subtle Ambient Background */}
          <div className="absolute top-10 right-10 w-96 h-96 bg-indigo-600/5 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-10 left-10 w-96 h-96 bg-cyan-600/5 rounded-full blur-3xl pointer-events-none" />
          <div className="relative z-10 max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
