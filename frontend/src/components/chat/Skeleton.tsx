'use client';

import clsx from 'clsx';
import React from 'react';

/** Base shimmer block. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('skeleton', className)} aria-hidden="true" />;
}

/** A line of shimmering text sized to the real copy it replaces. */
export function SkeletonText({
  lines = 1,
  className,
  widths,
}: {
  lines?: number;
  className?: string;
  widths?: number[];
}) {
  return (
    <div className={clsx('space-y-2', className)} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="skeleton h-3"
          style={{ width: `${widths?.[i] ?? 100 - i * 12}%` }}
        />
      ))}
    </div>
  );
}

/** Placeholder for one conversation in the history sidecar. */
export function HistorySkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-1.5" role="status" aria-label="Loading conversations">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="p-2.5 rounded-sm border border-transparent">
          <div className="flex items-center gap-1.5">
            {i === 0 && <Skeleton className="w-1.5 h-1.5 rounded-full" />}
            <Skeleton className="h-3 flex-1" />
          </div>
          <div className="flex items-center gap-2 mt-2">
            <Skeleton className="h-2 w-16" />
            <Skeleton className="h-2 w-10" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Placeholder chat bubble pair shown while a conversation hydrates. */
export function ThreadSkeleton() {
  return (
    <div className="space-y-5 py-2" role="status" aria-label="Loading conversation">
      <div className="flex justify-end">
        <div className="space-y-2 w-2/3 max-w-sm">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-3/4 ml-auto" />
        </div>
      </div>
      <div className="flex justify-start">
        <div className="space-y-2 w-4/5 max-w-lg">
          <Skeleton className="h-3 w-24" />
          <SkeletonText lines={4} widths={[96, 88, 92, 54]} />
        </div>
      </div>
      <div className="flex justify-start">
        <div className="space-y-2 w-3/5 max-w-md">
          <Skeleton className="h-3 w-24" />
          <SkeletonText lines={3} widths={[90, 82, 40]} />
        </div>
      </div>
    </div>
  );
}

/** Placeholder for the artifacts zone while build history loads. */
export function ArtifactsSkeleton({ count = 2 }: { count?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading builds">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="sutra-card p-4 space-y-3">
          <div className="flex items-center gap-3">
            <Skeleton className="w-9 h-9" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="h-2 w-20" />
            </div>
            <Skeleton className="h-4 w-14" />
          </div>
          <Skeleton className="h-1.5 w-full" />
        </div>
      ))}
    </div>
  );
}

/** Shimmering assistant bubble shown while the orchestrator is composing. */
export function ThinkingBubble() {
  return (
    <div className="flex items-start gap-3 animate-fade-in" role="status" aria-live="polite">
      <Skeleton className="w-6 h-6 rounded-full shrink-0" />
      <div className="flex-1 min-w-0 space-y-2 pt-1">
        <div className="flex items-center gap-2">
          <Skeleton className="h-2.5 w-24" />
        </div>
        <SkeletonText lines={2} widths={[88, 62]} />
      </div>
    </div>
  );
}
