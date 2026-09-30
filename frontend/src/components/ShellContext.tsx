'use client';

import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

type ShellState = {
  /** Docked rail: false is the 64px icon-only layout. */
  railExpanded: boolean;
  setRailExpanded: (expanded: boolean) => void;
  /** Mobile nav drawer. */
  navOpen: boolean;
  setNavOpen: (open: boolean) => void;
};

const ShellContext = createContext<ShellState | null>(null);

/**
 * Shell chrome state that has to be shared between the navbar and the rail.
 *
 * The rail itself owns nothing: the navbar renders the toggle, so the expanded
 * flag has to live above both. That is also what makes the rail reopenable on
 * desktop, where the navbar's toggle is always visible.
 */
export function ShellProvider({ children }: { children: ReactNode }) {
  const [railExpanded, setRailExpanded] = useState(true);
  const [navOpen, setNavOpen] = useState(false);

  const value = useMemo(
    () => ({ railExpanded, setRailExpanded, navOpen, setNavOpen }),
    [railExpanded, navOpen],
  );

  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}

export function useShell(): ShellState {
  const context = useContext(ShellContext);
  if (!context) throw new Error('useShell must be used inside ShellProvider');
  return context;
}
