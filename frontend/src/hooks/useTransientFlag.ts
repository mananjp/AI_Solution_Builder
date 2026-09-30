'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * A boolean flag that resets itself after `durationMs`.
 *
 * Replaces the `setTimeout(() => setFlag(false), n)` + bare `setState(true)`
 * pattern that was repeated across the settings, billing and sandbox screens.
 * Two problems with the inline version: the timer was never cleared, so a fast
 * navigation left it to fire against an unmounted component, and because the
 * reset was scheduled from the *same* tick that set the flag, a second trigger
 * inside the window produced a wrong "Saved" label for an edit that had not
 * actually been saved.
 *
 * Restarting the window cancels the previous timer first, so the flag always
 * reflects the most recent trigger.
 */
export function useTransientFlag(durationMs: number, initial = false) {
  const [active, setActive] = useState(initial);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clear = useCallback(() => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const trigger = useCallback(() => {
    clear();
    setActive(true);
    timer.current = setTimeout(() => {
      timer.current = null;
      setActive(false);
    }, durationMs);
  }, [clear, durationMs]);

  const reset = useCallback(() => {
    clear();
    setActive(false);
  }, [clear]);

  useEffect(() => clear, [clear]);

  return { active, trigger, reset, setActive } as const;
}