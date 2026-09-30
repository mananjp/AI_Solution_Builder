'use client';

import Link from 'next/link';

import { CollapsibleSidebar } from '@/components/lab/collapsible-sidebar';
import { useNavItems } from '@/components/nav-items';
import { useShell } from '@/components/ShellContext';

/**
 * Docked navigation rail.
 *
 * Built on the lab's `CollapsibleSidebar`, which animates the rail's width
 * rather than scaling it, so labels and icons are never squashed mid-transition.
 * The active row's highlight is a shared layout element, so moving between
 * items slides the highlight instead of cross-fading it, and a collapsed row
 * raises its label as a tooltip on hover and on keyboard focus.
 *
 * The lab component ships its own toggle inside a children column. This rail is
 * full-bleed and the navbar owns that toggle, so the column is hidden here
 * rather than left as a second, redundant control.
 */
export default function AppSidebar() {
  const items = useNavItems();
  const { railExpanded, setRailExpanded } = useShell();

  const railItems = items.map((item) => ({
    id: item.key,
    label: item.label,
    icon: <item.icon className="size-5" aria-hidden />,
    // Without this the rows render as buttons wired to a no-op and nothing
    // navigates. The rail is controlled on `id`, but each row still needs its
    // destination so it can be a real link.
    href: item.href,
  }));

  // The rail is controlled on an id, but navigation happens through links, so
  // this only drives which row is highlighted.
  const currentId = items.find((item) => item.active)?.key ?? items[0]?.key ?? '';

  return (
    // No width and no right border here.
    //
    // The lab's `motion.nav` animates its own width between 64 and 240 and owns
    // its trailing border. This wrapper used to hard-code `w-16`/`w-60` and add a
    // second `border-r`, which meant the aside snapped to the final width on the
    // same frame the toggle was pressed while the rail was still springing — so
    // the content column jumped first and the rail caught up, and two 1px rules
    // sat on top of each other. Sizing to the lab's own nav lets the spring
    // drive the reflow, so the column follows the rail instead of racing it.
    <div className="flex h-full flex-col bg-background">
      {/* The wordmark is outside the animated nav, so at full size it would hold
          the collapsed rail wider than its 64px and the icons would sit off-centre.
          It is only rendered when there is room for it, and the row keeps its
          height either way so nothing jumps on toggle. */}
      <div className="flex h-14 shrink-0 items-center px-3">
        {railExpanded && (
          <Link
            href="/dashboard"
            className="font-sanskrit text-xl font-bold leading-none text-foreground"
          >
            सूत्र
          </Link>
        )}
      </div>

      {/* No horizontal padding: the lab already pads its own list with `p-2`, and
          the extra 8px here pushed a 48px row to 80px inside the 64px collapsed
          rail, so the icon was off-centre and clipped on the right. */}
      <div className="min-h-0 flex-1 pb-2 [&>div>div:last-child]:hidden">
        <CollapsibleSidebar
          items={railItems}
          value={currentId}
          onChange={() => undefined}
          expanded={railExpanded}
          onExpandedChange={setRailExpanded}
          className="h-full w-full rounded-none border-0 bg-transparent p-0 shadow-none"
        />
      </div>
    </div>
  );
}
