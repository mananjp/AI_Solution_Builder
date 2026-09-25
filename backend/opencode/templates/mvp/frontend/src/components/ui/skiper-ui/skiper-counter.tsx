"use client";

import React, { useEffect, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

export interface SkiperCounterProps {
  value: number;
  direction?: "up" | "down";
  className?: string;
  prefix?: string;
  suffix?: string;
}

export const SkiperCounter: React.FC<SkiperCounterProps> = ({
  value,
  className,
  prefix = "",
  suffix = "",
}) => {
  const spring = useSpring(0, { mass: 0.8, stiffness: 75, damping: 15 });
  const display = useTransform(spring, (current) => Math.round(current).toLocaleString());
  const [displayValue, setDisplayValue] = useState<string>("0");

  useEffect(() => {
    spring.set(value);
  }, [spring, value]);

  useEffect(() => {
    const unsubscribe = display.on("change", (latest) => {
      setDisplayValue(latest);
    });
    return () => unsubscribe();
  }, [display]);

  return (
    <span className={className}>
      {prefix}
      <motion.span>{displayValue}</motion.span>
      {suffix}
    </span>
  );
};
