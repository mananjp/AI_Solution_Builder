"use client";

import {
  useCallback,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { PanelLeft } from "lucide-react";

import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";

/**
 * Sidecar panel whose width is set by dragging its inner edge.
 *
 * Dragging is pointer-based rather than a layout library because the wanted
 * behaviour is not a resize: pulling the panel past `hideBelow` closes it
 * outright and springs it away, and pushing back from the tab reopens it at the
 * width it had before. A resizable-panels group clamps at its minimum instead,
 * so the panel would sit at a stub and never dismiss.
 *
 * The handle is a real `separator` with `aria-valuenow`, and responds to the
 * arrow keys, so the width is reachable without a pointer.
 */

const STORAGE_KEY = "sutra.chat.sidecarWidth";
const MIN = 240;
const MAX = 560;
/** Below this the drag is read as "get this out of my way". */
const HIDE_BELOW = 120;
const DEFAULT = 340;

function readStoredWidth(): number {
  if (typeof window === "undefined") return DEFAULT;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return DEFAULT;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n >= MIN && n <= MAX ? n : DEFAULT;
}

/**
 * Subscribe to the persisted width.
 *
 * The value lives in localStorage, which emits no events, so this listens for
 * the window focus that can follow a change made in another tab. The notification
 * is a nudge to re-read; it carries no data.
 */
function subscribeWidth(onChange: () => void): () => void {
  window.addEventListener("focus", onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener("focus", onChange);
    window.removeEventListener("storage", onChange);
  };
}

interface ResizableSidecarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
  label: string;
  className?: string;
}

export function ResizableSidecar({
  open,
  onOpenChange,
  children,
  label,
  className,
}: ResizableSidecarProps) {
  // The persisted width is an external store, so it is read with
  // `useSyncExternalStore` rather than copied into state by an effect. That
  // avoids the cascading render the linter flags, and it is the same pattern the
  // app already uses for `prefers-reduced-motion`. The server snapshot is
  // DEFAULT, so SSR and the first client render agree and there is no hydration
  // mismatch; the stored value applies from the following commit, which is
  // invisible because the panel has no CSS width transition.
  const persistedWidth = useSyncExternalStore(
    subscribeWidth,
    readStoredWidth,
    () => DEFAULT
  );

  // Non-null while the pointer owns the width, so a drag is not fought by the
  // persisted value mid-gesture.
  const [liveWidth, setLiveWidth] = useState<number | null>(null);
  const width = liveWidth ?? persistedWidth;

  const panelId = useId();

  const persist = useCallback((next: number) => {
    setLiveWidth(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(next));
    } catch {
      // Private browsing can refuse writes. The width still holds for this view.
    }
  }, []);

  const drag = useRef<{ startX: number; startWidth: number } | null>(null);

  const endDrag = useCallback(
    (commit: boolean) => {
      const start = drag.current;
      drag.current = null;
      document.body.style.removeProperty("cursor");
      document.body.style.removeProperty("user-select");
      if (!start || !commit) return;

      // Read the live width: the pointer may have moved past the threshold and
      // been clamped while the drag was still active.
      setLiveWidth((current) => {
        const w = current ?? DEFAULT;
        if (w < HIDE_BELOW) {
          onOpenChange(false);
          // Reset so reopening starts from the default rather than the stub
          // width that triggered the dismissal.
          return null;
        }
        return w;
      });
    },
    [onOpenChange]
  );

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { startX: e.clientX, startWidth: width };
    // Keeps the resize cursor and the text-selection block for the whole drag,
    // including when the pointer leaves the 6px handle.
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const start = drag.current;
    if (!start) return;
    // The handle is on the panel's right edge, so dragging left widens it.
    const next = Math.min(MAX, Math.max(0, start.startWidth - (e.clientX - start.startX)));
    setLiveWidth(next);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    const step = e.shiftKey ? 32 : 8;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      const next = Math.min(MAX, width + step);
      if (next >= HIDE_BELOW) persist(next);
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      const next = Math.max(0, width - step);
      if (next < HIDE_BELOW) onOpenChange(false);
      else persist(next);
    } else if (e.key === "Escape") {
      onOpenChange(false);
    }
  };

  if (!open) {
  return (
    <div className={cn("flex shrink-0", className)}>
      {/* Reopen affordance. A full-height strip rather than a floating button,
          so it lines up with the panel it restores. */}
        <Button variant="outline" size="icon-sm"
          type="button"
          onClick={() => onOpenChange(true)}
          aria-label={`Show ${label}`}
          aria-expanded={false}
          aria-controls={panelId}
          className="flex h-full w-8 shrink-0 cursor-pointer items-start justify-center self-stretch border-r border-border bg-surface/50 pt-3 text-muted transition-colors hover:bg-surface hover:text-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-solid focus-visible:outline-foreground"
        >
          <PanelLeft className="size-4" aria-hidden />
        </Button>
      </div>
    );
  }

  return (
    <div className={cn("relative flex shrink-0", className)} style={{ width }}>
      <aside
        id={panelId}
        aria-label={label}
        className="flex min-h-0 w-full flex-col overflow-hidden border-r border-border"
      >
        {children}
      </aside>

      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={`Resize ${label}`}
        aria-valuenow={Math.round(width)}
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        tabIndex={0}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={() => endDrag(true)}
        onPointerCancel={() => endDrag(false)}
        onLostPointerCapture={() => endDrag(true)}
        onKeyDown={onKeyDown}
        onDoubleClick={() => onOpenChange(false)}
        className={cn(
          "absolute inset-y-0 -right-1 z-20 w-2 cursor-col-resize touch-none",
          "after:absolute after:inset-y-0 after:left-1/2 after:w-px after:-translate-x-1/2 after:bg-transparent after:transition-colors",
          "hover:after:bg-border-2 focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-solid focus-visible:outline-foreground",
        )}
      />
    </div>
  );
}
