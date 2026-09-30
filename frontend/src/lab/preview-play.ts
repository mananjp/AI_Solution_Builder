"use client"

/**
 * The lab set gates every animation behind a preview player, so nothing moved
 * until you pressed play in the lab page itself. The hook returned:
 *
 *   true      animate
 *   false     pinned still (the preview was paused)
 *   undefined inert, never animate
 *
 * There is no preview player in the app, so there is nothing to gate on. This
 * returns true: animations run off the real interaction that triggers them.
 */
export function usePreviewPlay(): boolean {
  return true
}
