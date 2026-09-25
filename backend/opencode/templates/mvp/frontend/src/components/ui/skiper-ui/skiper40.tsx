"use client";

import Link from "next/link";
import React from "react";
import { cn } from "@/lib/utils";

const Skiper40 = () => {
  return (
    <section className="h-full snap-y snap-mandatory overflow-y-scroll">
      <div className="relative flex h-full w-full flex-col items-center justify-center gap-5">
        <Link001 href="#">Explore Platform</Link001>
        <Link002 href="#">View Documentation</Link002>
        <Link003 href="#">Live Services</Link003>
        <Link004 href="#">Admin Console</Link004>
        <Link005 href="#">Get Started</Link005>
      </div>
    </section>
  );
};

export { Link000, Link001, Link002, Link003, Link004, Link005, Skiper40 };

const Link000 = ({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href: string;
  className?: string;
}) => {
  return (
    <Link
      href={href}
      className={cn(
        "group relative flex items-center font-medium",
        className,
        "before:pointer-events-none before:absolute before:bottom-0 before:left-0 before:h-[0.08em] before:w-full before:bg-current before:content-['']",
        "before:origin-right before:scale-x-0 before:transition-transform before:duration-300 before:ease-[cubic-bezier(0.4,0,0.2,1)]",
        "hover:before:origin-left hover:before:scale-x-100",
      )}
    >
      {children}
    </Link>
  );
};

const Link001 = ({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href: string;
  className?: string;
}) => {
  return (
    <Link
      href={href}
      className={cn(
        "group relative inline-flex items-center font-medium",
        "before:pointer-events-none before:absolute before:left-0 before:top-[1.4em] before:h-[0.08em] before:w-full before:bg-current before:content-['']",
        "before:origin-right before:scale-x-0 before:transition-transform before:duration-300 before:ease-[cubic-bezier(0.4,0,0.2,1)]",
        "hover:before:origin-left hover:before:scale-x-100",
        className,
      )}
    >
      {children}
      <svg
        className="ml-[0.35em] mt-[0em] size-[0.75em] translate-y-0.5 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100"
        fill="none"
        viewBox="0 0 10 10"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M1.004 9.166 9.337.833m0 0v8.333m0-8.333H1.004"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </Link>
  );
};

const Link002 = ({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href: string;
  className?: string;
}) => {
  return (
    <Link
      href={href}
      className={cn(
        "group relative inline-flex items-center font-medium",
        className,
        "before:pointer-events-none before:absolute before:left-0 before:top-[1.4em] before:h-[0.08em] before:w-full before:bg-current before:content-['']",
        "before:origin-right before:scale-x-0 before:transition-transform before:duration-300 before:ease-[cubic-bezier(0.4,0,0.2,1)]",
        "before:origin-left",
        "hover:before:origin-right hover:before:scale-x-100",
      )}
    >
      {children}
      <svg
        className="ml-[0.35em] mt-[0em] size-[0.75em] translate-y-0.5 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100"
        fill="none"
        viewBox="0 0 10 10"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M1.004 9.166 9.337.833m0 0v8.333m0-8.333H1.004"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </Link>
  );
};

const Link003 = ({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href: string;
  className?: string;
}) => {
  return (
    <Link
      href={href}
      className={cn(
        "group relative inline-flex items-center font-medium",
        className,
        "before:pointer-events-none before:absolute before:left-0 before:top-[1.4em] before:h-[0.08em] before:w-full before:bg-current before:content-['']",
        "before:origin-right before:scale-x-0 before:transition-transform before:duration-300 before:ease-[cubic-bezier(0.4,0,0.2,1)]",
        "before:origin-center",
        "hover:before:scale-x-100",
      )}
    >
      {children}
      <svg
        className="ml-[0.35em] mt-[0em] size-[0.75em] translate-y-0.5 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100"
        fill="none"
        viewBox="0 0 10 10"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M1.004 9.166 9.337.833m0 0v8.333m0-8.333H1.004"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </Link>
  );
};

const Link004 = ({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href: string;
  className?: string;
}) => {
  return (
    <Link
      href={href}
      className={cn(
        "group relative inline-flex items-center font-medium",
        className,
        "before:pointer-events-none before:absolute before:left-0 before:w-full before:bg-indigo-600/10 before:content-['']",
        "before:origin-right before:scale-x-0 before:transition-all before:duration-300 before:ease-[cubic-bezier(0.4,0,0.2,1)]",
        "before:origin-center md:before:bottom-0 rounded-md",
        "px-2 py-0.5 before:h-0 before:scale-x-100 hover:before:h-full",
      )}
    >
      {children}
      <svg
        className="ml-[0.35em] mt-[0em] size-[0.75em] translate-y-0.5 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:rotate-45 group-hover:opacity-100"
        fill="none"
        viewBox="0 0 10 10"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M1.004 9.166 9.337.833m0 0v8.333m0-8.333H1.004"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </Link>
  );
};

const Link005 = ({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href: string;
  className?: string;
}) => {
  return (
    <Link
      href={href}
      className={cn(
        className,
        "group relative inline-flex items-center font-medium",
        "before:pointer-events-none before:absolute before:left-0 before:w-full before:bg-indigo-500/10 before:content-[''] rounded-md",
        "before:scale-x-1 before:transition-all before:duration-300 before:ease-[cubic-bezier(0.4,0,0.2,1)]",
        "before:origin-left md:before:top-0",
        "px-2 py-0.5 before:h-full before:scale-x-0 hover:before:scale-x-100",
      )}
    >
      {children}
      <svg
        className="ml-[0.35em] mt-[0em] size-[0.75em] -translate-x-1 rotate-45 opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100"
        fill="none"
        viewBox="0 0 10 10"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path
          d="M1.004 9.166 9.337.833m0 0v8.333m0-8.333H1.004"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </Link>
  );
};
