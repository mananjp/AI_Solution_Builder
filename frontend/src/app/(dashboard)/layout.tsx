'use client';

import React from 'react';
import Sidebar from '@/components/Sidebar';
import Navbar from '@/components/Navbar';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#f5f5f5]">
      <Sidebar />
      <div className="flex min-h-screen flex-col lg:pl-[240px]">
        <Navbar />
        <main className="flex-1 p-6 lg:p-8 max-w-[1280px] w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
