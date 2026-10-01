# ADR 0005: Domain-Aware Theme Engine & Industry Palettes

- **Status**: Accepted
- **Date**: 2026-10-01
- **Feature**: Dynamic Theme Engine & Industry Palettes
- **Deciders**: Engineering & Architecture Team

---

## Context

Generated applications frequently suffered from generic, sterile styling (e.g. basic Bootstrap-like blue buttons and stark white backgrounds) regardless of the domain. An artisan ice cream shop, a medical patient portal, an enterprise logistics tool, and a luxury hospitality landing page all looked identical.

Manual theme selection was cumbersome for users during prompt-based creation, while relying on random color pickers caused severe WCAG accessibility contrast failures and disjointed UI aesthetics.

---

## Decision

We implemented `backend/app/services/theme_engine.py` providing automated domain classification and harmonious design token synthesis:

1. **`INDUSTRY_PALETTES`**:
   - Curated, high-contrast, professional design palettes across major industry verticals:
     - `food_beverage` (Warm amber, cream, terracotta)
     - `healthcare` (Teal, mint, clean slate)
     - `fintech` (Deep sapphire, emerald, navy)
     - `ecommerce` (Modern indigo, coral, neutral zinc)
     - `saas_enterprise` (Modern cobalt, slate, violet)
     - `fitness_wellness` (Energizing emerald, lime, charcoal)
     - `creative_portfolio` (Sleek monochrome, electric purple)
     - `real_estate` (Warm stone, bronze, forest green)

2. **Automatic Domain Heuristic Classification (`classify_vertical`)**:
   - Analyzes user prompts and entity keywords (e.g. "ice cream", "gelato", "dessert" -> `food_beverage`; "clinic", "patient", "doctor" -> `healthcare`).
   - Assigns the vertical and derives complementary primary, secondary, accent, surface, and text colors.

3. **Accessibility & Contrast Verification**:
   - Validates WCAG AA / AAA relative luminance contrast ratios for text on backgrounds.
   - Automatically shifts text color to dark charcoal or crisp white depending on the surface luminance.

4. **Dynamic CSS Token Generation (`apply_theme`)**:
   - Emits CSS variables (`--color-primary`, `--color-secondary`, `--color-accent`, `--color-bg`, `--color-text`) directly into `styles/theme.css` and Next.js root layout.

---

## Consequences

### Positive
- Instant visual delight: generated apps immediately look tailored to their business domain without manual tuning.
- Built-in accessibility: guaranteed contrast compliance out of the box.
- Seamless developer override: tokens are standard CSS variables easily modified in Tailwind or CSS modules.

### Limitations & Trade-offs
- Keyword classification relies on heuristics; novel or highly ambiguous verticals may fall back to default SaaS indigo unless explicitly overridden via `AppSpec`.
