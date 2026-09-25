"use client";

import React, { useRef, useState } from "react";
import { motion, HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/utils";

export interface SkiperCardProps extends HTMLMotionProps<"div"> {
  children: React.ReactNode;
  glow?: boolean;
  interactive?: boolean;
}

export const SkiperCard = React.forwardRef<HTMLDivElement, SkiperCardProps>(
  ({ className, children, glow = true, interactive = true, ...props }, ref) => {
    const cardRef = useRef<HTMLDivElement | null>(null);
    const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
    const [isHovered, setIsHovered] = useState(false);

    const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
      if (!glow || !cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      setMousePosition({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    };

    return (
      <motion.div
        ref={(node) => {
          cardRef.current = node;
          if (typeof ref === "function") ref(node);
          else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
        }}
        onMouseMove={handleMouseMove}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        whileHover={interactive ? { y: -3, transition: { duration: 0.2 } } : undefined}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        className={cn(
          "relative overflow-hidden rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm transition-shadow",
          interactive && "hover:shadow-lg hover:shadow-indigo-500/5 hover:border-indigo-300/80",
          className,
        )}
        {...props}
      >
        {glow && isHovered && (
          <div
            className="pointer-events-none absolute -inset-px opacity-100 transition-opacity duration-300"
            style={{
              background: `radial-gradient(400px circle at ${mousePosition.x}px ${mousePosition.y}px, rgba(99, 102, 241, 0.08), transparent 80%)`,
            }}
          />
        )}
        <div className="relative z-10">{children}</div>
      </motion.div>
    );
  },
);

SkiperCard.displayName = "SkiperCard";
