"use client";

import { useState } from "react";

import { cn } from "@/lib/cn";

function initialsOf(name: string, email: string): string {
  const source = name.trim() || email.trim();
  if (!source) return "?";
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}

interface UserAvatarProps {
  name?: string;
  email?: string;
  /** Auth0 `picture` claim. Absent for most connections. */
  src?: string | null;
  size?: number;
  className?: string;
}

/**
 * Profile image with an initials fallback.
 *
 * The signed-in identity often has no picture: Auth0 only issues the `picture`
 * claim for connections that supply one, so a Gravatar URL cannot be assumed.
 * The initials are therefore the normal case and the image is the enhancement.
 *
 * A plain `<img>` rather than `next/image`, because the URL is an arbitrary
 * remote host and this app configures no `remotePatterns`. An image that fails
 * to load falls back to initials rather than leaving a broken glyph.
 */
export function UserAvatar({
  name,
  email,
  src,
  size = 28,
  className,
}: UserAvatarProps) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  const initials = initialsOf(name ?? "", email ?? "");
  const showImage = Boolean(src) && failedSrc !== src;

  return (
    <span
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-primary font-serif text-primary-foreground select-none",
        className,
      )}
      style={{ width: size, height: size, fontSize: Math.max(9, Math.round(size * 0.38)) }}
    >
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src as string}
          alt=""
          className="size-full object-cover"
          referrerPolicy="no-referrer"
          onError={() => setFailedSrc(src ?? null)}
        />
      ) : (
        <span aria-hidden>{initials}</span>
      )}
    </span>
  );
}
