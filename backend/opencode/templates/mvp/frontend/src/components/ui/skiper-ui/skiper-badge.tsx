"use client";

import React from "react";
import { cn } from "@/lib/utils";

export interface SkiperBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: "success" | "warning" | "info" | "neutral" | "danger" | "purple";
  pulse?: boolean;
  children: React.ReactNode;
}

export const SkiperBadge: React.FC<SkiperBadgeProps> = ({
  className,
  variant = "success",
  pulse = true,
  children,
  ...props
}) => {
  const variantStyles = {
    success: "bg-emerald-50 text-emerald-700 border-emerald-200/80",
    warning: "bg-amber-50 text-amber-700 border-amber-200/80",
    info: "bg-sky-50 text-sky-700 border-sky-200/80",
    neutral: "bg-slate-100 text-slate-700 border-slate-200",
    danger: "bg-rose-50 text-rose-700 border-rose-200/80",
    purple: "bg-indigo-50 text-indigo-700 border-indigo-200/80",
  };

  const dotColors = {
    success: "bg-emerald-500",
    warning: "bg-amber-500",
    info: "bg-sky-500",
    neutral: "bg-slate-400",
    danger: "bg-rose-500",
    purple: "bg-indigo-500",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold tracking-wide transition-colors",
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      {pulse && (
        <span className="relative flex h-2 w-2">
          <span
            className={cn(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              dotColors[variant],
            )}
          />
          <span className={cn("relative inline-flex h-2 w-2 rounded-full", dotColors[variant])} />
        </span>
      )}
      {children}
    </span>
  );
};
