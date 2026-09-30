/**
 * Class-name merge helper.
 *
 * Re-exports the `cn` package. The `cn` specifier here must stay a bare import:
 * this file is what `@/lib/cn` resolves to, so writing `@/lib/cn` inside it would
 * make the alias point at itself.
 */
export { cn } from "cn"
