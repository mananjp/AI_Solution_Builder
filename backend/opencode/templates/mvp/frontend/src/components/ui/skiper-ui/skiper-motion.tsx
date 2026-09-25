"use client";

import React from "react";
import { motion, HTMLMotionProps, Variants } from "framer-motion";

export const StaggerContainer: React.FC<
  HTMLMotionProps<"div"> & { delayChildren?: number; staggerChildren?: number }
> = ({ children, delayChildren = 0.05, staggerChildren = 0.08, className, ...props }) => {
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        delayChildren,
        staggerChildren,
      },
    },
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="show"
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export const FadeIn: React.FC<
  HTMLMotionProps<"div"> & { delay?: number; duration?: number }
> = ({ children, delay = 0, duration = 0.35, className, ...props }) => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration, delay, ease: "easeOut" }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export const SlideUp: React.FC<
  HTMLMotionProps<"div"> & { delay?: number; y?: number }
> = ({ children, delay = 0, y = 16, className, ...props }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.16, 1, 0.3, 1] }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
};

export const ScaleIn: React.FC<
  HTMLMotionProps<"div"> & { delay?: number; scale?: number }
> = ({ children, delay = 0, scale = 0.95, className, ...props }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.35, delay, ease: [0.16, 1, 0.3, 1] }}
      className={className}
      {...props}
    >
      {children}
    </motion.div>
  );
};
