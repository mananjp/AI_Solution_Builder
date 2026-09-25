"use client";

import React from "react";
import { motion, HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

export interface SkiperButtonProps extends HTMLMotionProps<"button"> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "glow" | "danger";
  size?: "sm" | "md" | "lg";
  children: React.ReactNode;
  icon?: React.ReactNode;
}

export const SkiperButton = React.forwardRef<HTMLButtonElement, SkiperButtonProps>(
  ({ className, variant = "primary", size = "md", children, icon, ...props }, ref) => {
    const baseStyles =
      "relative inline-flex items-center justify-center font-medium rounded-xl transition-all overflow-hidden focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:opacity-50 disabled:pointer-events-none cursor-pointer";

    const sizeStyles = {
      sm: "px-3 py-1.5 text-xs gap-1.5",
      md: "px-4 py-2 text-sm gap-2",
      lg: "px-6 py-2.5 text-base gap-2.5 font-semibold",
    };

    const variantStyles = {
      primary:
        "bg-slate-900 text-white hover:bg-slate-800 shadow-sm hover:shadow-md hover:shadow-slate-900/10 active:bg-slate-950",
      secondary:
        "bg-indigo-50 text-indigo-700 hover:bg-indigo-100/80 border border-indigo-200/60 shadow-sm",
      outline:
        "bg-white text-slate-700 border border-slate-200 hover:border-slate-300 hover:bg-slate-50/80 shadow-sm",
      ghost: "text-slate-600 hover:text-slate-900 hover:bg-slate-100/70",
      glow: "bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40 hover:brightness-105",
      danger: "bg-rose-600 text-white hover:bg-rose-700 shadow-sm shadow-rose-500/20",
    };

    return (
      <motion.button
        ref={ref}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
        className={cn(baseStyles, sizeStyles[size], variantStyles[variant], className)}
        {...props}
      >
        {variant === "glow" && (
          <span className="absolute inset-0 bg-white/20 translate-x-[-100%] hover:translate-x-[100%] transition-transform duration-700 ease-in-out pointer-events-none" />
        )}
        {icon && <span className="shrink-0">{icon}</span>}
        <span>{children}</span>
      </motion.button>
    );
  },
);

SkiperButton.displayName = "SkiperButton";
