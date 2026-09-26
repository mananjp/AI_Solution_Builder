"""
AI Solution Builder — Legacy Repository Read-Only Inspector & Architecture Analyzer

Performs a comprehensive, deep-inspection of an existing/outdated codebase:
- Directory & Manifest parsing
- Stack & Framework detection
- Architecture & Entry Point tracing
- Asset & Resource cataloging (logos, icons, SVGs, design tokens)
- Legacy pattern & technical debt detection
- Reusable code identification
- Structured Phased Modernization Planning
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from app.services.legacy_repo.boundary import assert_safe_boundary

logger = logging.getLogger(__name__)

# Ignored directories for deep code analysis
IGNORED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".next",
    "dist",
    "build",
    "venv",
    ".venv",
    "env",
    ".env_virtual",
    ".gradle",
    "target",
    "vendor",
}

ASSET_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".webp",
    ".gif",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".webm",
}


class LegacyRepoAnalyzer:
    """Read-only static analyzer and architectural tracer for legacy codebases."""

    def __init__(self, repo_dir: Path | str):
        self.root = assert_safe_boundary(repo_dir, action="analyze")
        if not self.root.exists() or not self.root.is_dir():
            raise FileNotFoundError(f"Repository directory does not exist: {self.root}")

    def analyze(self) -> dict[str, Any]:
        """Perform end-to-end read-only inspection and return structured report."""
        structure = self._inspect_structure()
        tech_stack = self._detect_technology_stack(structure)
        entry_points = self._discover_entry_points(tech_stack)
        architecture = self._trace_architecture(tech_stack, entry_points)
        assets = self._discover_assets()
        debt = self._detect_legacy_patterns_and_debt(tech_stack)
        reusable = self._identify_reusable_elements(structure, assets, tech_stack)
        modernization_plan = self._build_modernization_plan(tech_stack, debt, reusable)

        return {
            "root_path": str(self.root),
            "project_name": self.root.name,
            "structure": structure,
            "technology_stack": tech_stack,
            "entry_points": entry_points,
            "architecture": architecture,
            "assets_inventory": assets,
            "technical_debt": debt,
            "reusable_elements": reusable,
            "modernization_plan": modernization_plan,
        }

    # ── 1. Structure Inspection ───────────────────────────────────────────

    def _inspect_structure(self) -> dict[str, Any]:
        """Scan directory tree, manifest files, and deployment descriptors."""
        directories: list[str] = []
        files: list[str] = []
        manifests: list[str] = []
        config_files: list[str] = []
        doc_files: list[str] = []
        test_files: list[str] = []

        manifest_patterns = {
            "package.json",
            "package-lock.json",
            "yarn.lock",
            "pnpm-lock.yaml",
            "requirements.txt",
            "Pipfile",
            "pyproject.toml",
            "setup.py",
            "poetry.lock",
            "pom.xml",
            "build.gradle",
            "settings.gradle",
            "composer.json",
            "composer.lock",
            "Gemfile",
            "Gemfile.lock",
            "go.mod",
            "go.sum",
            "Cargo.toml",
            "Cargo.lock",
        }

        config_patterns = {
            "docker-compose.yml",
            "docker-compose.yaml",
            "Dockerfile",
            "render.yaml",
            "fly.toml",
            "vercel.json",
            "netlify.toml",
            "tsconfig.json",
            "jsconfig.json",
            "webpack.config.js",
            "vite.config.ts",
            "vite.config.js",
            "next.config.js",
            "next.config.ts",
            "next.config.mjs",
            ".babelrc",
            "babel.config.js",
            "tailwind.config.js",
            "tailwind.config.ts",
            "alembic.ini",
            "prisma/schema.prisma",
            ".env.example",
            ".env",
        }

        for path in self.root.rglob("*"):
            rel_parts = path.relative_to(self.root).parts
            if any(part in IGNORED_DIRS for part in rel_parts):
                continue

            rel_str = str(path.relative_to(self.root)).replace("\\", "/")
            if path.is_dir():
                directories.append(rel_str)
            elif path.is_file():
                files.append(rel_str)
                name = path.name
                if name in manifest_patterns or path.name.endswith(".lock"):
                    manifests.append(rel_str)
                elif (
                    name in config_patterns
                    or name.startswith("tsconfig")
                    or name.startswith(".env")
                ):
                    config_files.append(rel_str)
                elif name.lower().startswith("readme") or name.endswith(".md"):
                    doc_files.append(rel_str)
                elif "test" in rel_str.lower() or "spec" in rel_str.lower():
                    test_files.append(rel_str)

        return {
            "total_files": len(files),
            "total_directories": len(directories),
            "sample_files": files[:60],
            "manifests": manifests,
            "configs": config_files,
            "docs": doc_files,
            "tests": test_files,
        }

    # ── 2. Technology Stack Detection ─────────────────────────────────────

    def _detect_technology_stack(self, structure: dict[str, Any]) -> dict[str, Any]:
        """Accurately identify languages, frameworks, DBs, and runtime from project manifests."""
        stack: dict[str, Any] = {
            "languages": [],
            "frontend_framework": None,
            "backend_framework": None,
            "database": None,
            "orm": None,
            "auth": None,
            "api_style": "REST",
            "styling": None,
            "state_management": None,
            "build_tools": [],
            "package_manager": None,
            "runtime": None,
            "manifest_dependencies": {},
        }

        # Check Node / JavaScript / TypeScript ecosystem
        pkg_file = self.root / "package.json"
        if pkg_file.exists():
            stack["languages"].append("JavaScript")
            stack["package_manager"] = "npm"
            if (self.root / "yarn.lock").exists():
                stack["package_manager"] = "yarn"
            elif (self.root / "pnpm-lock.yaml").exists():
                stack["package_manager"] = "pnpm"

            if (self.root / "tsconfig.json").exists() or any(
                f.endswith(".ts") or f.endswith(".tsx") for f in structure.get("sample_files", [])
            ):
                stack["languages"].append("TypeScript")

            try:
                pkg_data = json.loads(pkg_file.read_text(encoding="utf-8", errors="ignore"))
                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                stack["manifest_dependencies"]["npm"] = deps

                # Frontend framework
                if "next" in deps:
                    stack["frontend_framework"] = f"Next.js ({deps.get('next', 'unknown')})"
                elif "react" in deps:
                    stack["frontend_framework"] = f"React ({deps.get('react', 'unknown')})"
                elif "vue" in deps or "nuxt" in deps:
                    stack["frontend_framework"] = (
                        f"Vue/Nuxt ({deps.get('vue', deps.get('nuxt', 'unknown'))})"
                    )
                elif "@angular/core" in deps:
                    stack["frontend_framework"] = (
                        f"Angular ({deps.get('@angular/core', 'unknown')})"
                    )
                elif "svelte" in deps:
                    stack["frontend_framework"] = "Svelte"

                # Backend framework (Node)
                if "express" in deps:
                    stack["backend_framework"] = f"Express.js ({deps.get('express', 'unknown')})"
                elif "@nestjs/core" in deps:
                    stack["backend_framework"] = "NestJS"
                elif "fastify" in deps:
                    stack["backend_framework"] = "Fastify"
                elif "koa" in deps:
                    stack["backend_framework"] = "Koa"

                # Database & ORM
                if "prisma" in deps or "@prisma/client" in deps:
                    stack["orm"] = "Prisma"
                elif "typeorm" in deps:
                    stack["orm"] = "TypeORM"
                elif "sequelize" in deps:
                    stack["orm"] = "Sequelize"
                elif "mongoose" in deps:
                    stack["database"] = "MongoDB"
                    stack["orm"] = "Mongoose"

                if "pg" in deps or "pg-promise" in deps:
                    stack["database"] = "PostgreSQL"
                elif "mysql" in deps or "mysql2" in deps:
                    stack["database"] = "MySQL"
                elif "sqlite3" in deps or "better-sqlite3" in deps:
                    stack["database"] = "SQLite"

                # Styling
                if "tailwindcss" in deps:
                    stack["styling"] = "Tailwind CSS"
                elif "styled-components" in deps:
                    stack["styling"] = "Styled Components"
                elif "sass" in deps or "node-sass" in deps:
                    stack["styling"] = "SASS/SCSS"
                elif "bootstrap" in deps:
                    stack["styling"] = "Bootstrap"

                # State Management
                if "redux" in deps or "@reduxjs/toolkit" in deps:
                    stack["state_management"] = "Redux"
                elif "zustand" in deps:
                    stack["state_management"] = "Zustand"
                elif "mobx" in deps:
                    stack["state_management"] = "MobX"

                # Auth
                if "next-auth" in deps or "@auth/core" in deps:
                    stack["auth"] = "NextAuth"
                elif "passport" in deps:
                    stack["auth"] = "Passport.js"
                elif "jsonwebtoken" in deps:
                    stack["auth"] = "JWT"
                elif "@supabase/supabase-js" in deps or "@supabase/auth-helpers-nextjs" in deps:
                    stack["auth"] = "Supabase Auth"
                    stack["database"] = stack["database"] or "Supabase (PostgreSQL)"

                # Build Tools
                for bt in ["webpack", "vite", "esbuild", "rollup", "babel-core", "turbo"]:
                    if bt in deps:
                        stack["build_tools"].append(bt)

            except Exception as exc:
                logger.warning("Could not fully parse package.json: %s", exc)

        # Check Python ecosystem
        req_file = self.root / "requirements.txt"
        pyproject = self.root / "pyproject.toml"
        pipfile = self.root / "Pipfile"
        python_files = list(self.root.rglob("*.py"))

        if req_file.exists() or pyproject.exists() or pipfile.exists() or python_files:
            if "Python" not in stack["languages"]:
                stack["languages"].append("Python")
            if not stack["package_manager"]:
                stack["package_manager"] = "pip"

            py_deps: dict[str, str] = {}
            if req_file.exists():
                text = req_file.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    cleaned = line.split("#")[0].strip()
                    if cleaned and not cleaned.startswith("-"):
                        parts = re.split(r"[><=~]+", cleaned, maxsplit=1)
                        pkg_n = parts[0].strip().lower()
                        ver = parts[1].strip() if len(parts) > 1 else "latest"
                        py_deps[pkg_n] = ver

            stack["manifest_dependencies"]["python"] = py_deps

            # Frameworks
            if "fastapi" in py_deps:
                stack["backend_framework"] = f"FastAPI ({py_deps.get('fastapi', 'unknown')})"
            elif "flask" in py_deps:
                stack["backend_framework"] = f"Flask ({py_deps.get('flask', 'unknown')})"
            elif "django" in py_deps:
                stack["backend_framework"] = f"Django ({py_deps.get('django', 'unknown')})"
            elif "tornado" in py_deps:
                stack["backend_framework"] = "Tornado"

            # DB & ORM
            if "sqlalchemy" in py_deps:
                stack["orm"] = f"SQLAlchemy ({py_deps.get('sqlalchemy', 'unknown')})"
            elif "tortoise-orm" in py_deps:
                stack["orm"] = "Tortoise ORM"
            elif "peewee" in py_deps:
                stack["orm"] = "Peewee"

            if "psycopg2" in py_deps or "asyncpg" in py_deps or "psycopg" in py_deps:
                stack["database"] = "PostgreSQL"
            elif "pymysql" in py_deps or "aiomysql" in py_deps:
                stack["database"] = "MySQL"
            elif "motor" in py_deps or "pymongo" in py_deps:
                stack["database"] = "MongoDB"
            elif "aiosqlite" in py_deps or "sqlite3" in py_deps:
                stack["database"] = "SQLite"

            if "jose" in py_deps or "jwt" in py_deps or "pyjwt" in py_deps:
                stack["auth"] = stack["auth"] or "JWT (Python)"

        # Check Java/Kotlin/PHP/Go
        if (self.root / "pom.xml").exists() or (self.root / "build.gradle").exists():
            stack["languages"].append("Java")
            stack["backend_framework"] = stack["backend_framework"] or "Spring Boot"
        if (self.root / "composer.json").exists():
            stack["languages"].append("PHP")
            stack["backend_framework"] = stack["backend_framework"] or "Laravel / PHP"
        if (self.root / "go.mod").exists():
            stack["languages"].append("Go")
            stack["backend_framework"] = stack["backend_framework"] or "Go Net/HTTP or Gin"

        return stack

    # ── 3. Application Entry Points Discovery ─────────────────────────────

    def _discover_entry_points(self, tech_stack: dict[str, Any]) -> dict[str, Any]:
        """Locate application entry points, routes, and main runtime files."""
        entry_points: dict[str, Any] = {
            "frontend_entry": None,
            "backend_entry": None,
            "routing_files": [],
            "database_schemas": [],
            "env_files": [],
        }

        # Check frontend entry
        fe_candidates = [
            "src/app/page.tsx",
            "src/pages/index.tsx",
            "pages/index.js",
            "src/App.tsx",
            "src/App.js",
            "src/main.tsx",
            "src/main.ts",
            "index.html",
            "public/index.html",
        ]
        for c in fe_candidates:
            if (self.root / c).exists():
                entry_points["frontend_entry"] = c
                break

        # Check backend entry
        be_candidates = [
            "main.py",
            "app.py",
            "server.py",
            "wsgi.py",
            "asgi.py",
            "backend/main.py",
            "src/server.ts",
            "src/index.ts",
            "server.js",
            "index.js",
            "app.js",
        ]
        for c in be_candidates:
            if (self.root / c).exists():
                entry_points["backend_entry"] = c
                break

        # Discover routing & schema files
        for path in self.root.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            name = path.name.lower()
            rel_str = str(path.relative_to(self.root)).replace("\\", "/")

            if name in ("routes.py", "routers.py", "routes.ts", "routes.js", "api.ts", "api.py"):
                entry_points["routing_files"].append(rel_str)
            elif name in ("models.py", "schemas.py", "schema.prisma", "schema.sql"):
                entry_points["database_schemas"].append(rel_str)
            elif name.startswith(".env"):
                entry_points["env_files"].append(rel_str)

        return entry_points

    # ── 4. Architecture Tracing ───────────────────────────────────────────

    def _trace_architecture(
        self, tech_stack: dict[str, Any], entry_points: dict[str, Any]
    ) -> dict[str, Any]:
        """Synthesize high-level structural model of the application."""
        has_fe = bool(tech_stack.get("frontend_framework") or entry_points.get("frontend_entry"))
        has_be = bool(tech_stack.get("backend_framework") or entry_points.get("backend_entry"))

        if has_fe and has_be:
            topology = "Decoupled Client-Server (Full-Stack)"
        elif has_fe and not has_be:
            topology = "Client-Only SPA / Static Web"
        elif has_be and not has_fe:
            topology = "Headless API / Microservice"
        else:
            topology = "Monolithic Script / Library"

        data_flow = []
        if has_fe:
            data_flow.append(f"Client UI ({tech_stack.get('frontend_framework') or 'Web'})")
        data_flow.append("API Layer (REST/HTTP)")
        if has_be:
            data_flow.append(f"Backend Server ({tech_stack.get('backend_framework') or 'Server'})")
        if tech_stack.get("database"):
            data_flow.append(f"Database ({tech_stack.get('database')})")

        return {
            "topology": topology,
            "data_flow": " -> ".join(data_flow),
            "frontend_present": has_fe,
            "backend_present": has_be,
            "database_present": bool(tech_stack.get("database")),
            "auth_present": bool(tech_stack.get("auth")),
        }

    # ── 5. Asset & Resource Discovery ─────────────────────────────────────

    def _discover_assets(self) -> dict[str, Any]:
        """Catalog logos, images, icons, fonts, design tokens, and media."""
        logos: list[str] = []
        icons: list[str] = []
        images: list[str] = []
        fonts: list[str] = []
        media: list[str] = []

        for path in self.root.rglob("*"):
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            if not path.is_file():
                continue

            rel_str = str(path.relative_to(self.root)).replace("\\", "/")
            suffix = path.suffix.lower()
            name_lower = path.name.lower()

            if suffix in ASSET_EXTENSIONS:
                if "logo" in name_lower or "brand" in name_lower:
                    logos.append(rel_str)
                elif "icon" in name_lower or "favicon" in name_lower:
                    icons.append(rel_str)
                elif suffix in (".woff", ".woff2", ".ttf", ".otf", ".eot"):
                    fonts.append(rel_str)
                elif suffix in (".mp3", ".wav", ".mp4", ".webm"):
                    media.append(rel_str)
                else:
                    images.append(rel_str)

        return {
            "total_assets": len(logos) + len(icons) + len(images) + len(fonts) + len(media),
            "logos": logos,
            "icons": icons,
            "images": images[:20],
            "fonts": fonts,
            "media": media,
            "reusable_message": "All existing branding, logos, and UI assets are indexed to be preserved verbatim.",
        }

    # ── 6. Legacy Code & Technical Debt Analysis ──────────────────────────

    def _detect_legacy_patterns_and_debt(self, tech_stack: dict[str, Any]) -> dict[str, Any]:
        """Identify outdated dependencies, deprecated APIs, security findings, and legacy patterns."""
        outdated_deps: list[dict[str, str]] = []
        legacy_patterns: list[dict[str, str]] = []
        security_findings: list[dict[str, str]] = []
        missing_infra: list[str] = []

        # Analyze NPM dependencies
        npm_deps = tech_stack.get("manifest_dependencies", {}).get("npm", {})
        deprecated_npm = {
            "request": "Deprecated in 2020. Replace with modern fetch or axios/ky.",
            "moment": "Deprecated. Replace with date-fns or native Intl / Temporal.",
            "babel-preset-es2015": "Obsolete. Replace with @babel/preset-env.",
            "node-sass": "Deprecated. Replace with dart-sass (sass).",
            "express": lambda v: (
                "Very old Express version (< 4.18)"
                if v and v.startswith(("^1", "^2", "^3", "1.", "2.", "3."))
                else None
            ),
            "react": lambda v: (
                "Legacy React (< 18). Lacks modern concurrent features & server components."
                if v and any(v.startswith(x) for x in ["^15", "^16", "15.", "16."])
                else None
            ),
            "next": lambda v: (
                "Legacy Next.js (< 13). Pages router only, lacks App Router."
                if v
                and any(
                    v.startswith(x) for x in ["^9", "^10", "^11", "^12", "9.", "10.", "11.", "12."]
                )
                else None
            ),
        }

        for pkg, info in deprecated_npm.items():
            if pkg in npm_deps:
                ver = npm_deps[pkg]
                reason = info(ver) if callable(info) else info
                if reason:
                    outdated_deps.append(
                        {"package": pkg, "current_version": str(ver), "reason": str(reason)}
                    )

        # Analyze Python dependencies
        py_deps = tech_stack.get("manifest_dependencies", {}).get("python", {})
        deprecated_py = {
            "urllib2": "Python 2 legacy library. Replace with httpx or requests.",
            "simplejson": "Legacy. Native json module is standard in Python 3.",
            "django": lambda v: (
                "Outdated Django (< 3.2)."
                if v and v.startswith(("1.", "2.", "3.0", "3.1"))
                else None
            ),
            "fastapi": lambda v: (
                "Old FastAPI (< 0.90)."
                if v and v.startswith("0.") and int(v.split(".")[1]) < 90
                else None
            ),
        }

        for pkg, info in deprecated_py.items():
            if pkg in py_deps:
                ver = py_deps[pkg]
                reason = info(ver) if callable(info) else info
                if reason:
                    outdated_deps.append(
                        {"package": pkg, "current_version": str(ver), "reason": str(reason)}
                    )

        # Scan code files for patterns (var, callback hell, hardcoded secrets, etc.)
        secret_pattern = re.compile(
            r"""(?:api_key|secret|password|bearer|auth_token)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]""",
            re.IGNORECASE,
        )
        var_pattern = re.compile(r"\bvar\s+[a-zA-Z0-9_]+\s*=")

        code_extensions = {".js", ".jsx", ".ts", ".tsx", ".py"}
        scanned_count = 0

        for path in self.root.rglob("*"):
            if (
                any(part in IGNORED_DIRS for part in path.parts)
                or path.suffix not in code_extensions
            ):
                continue
            if scanned_count > 100:  # Sample bounded set
                break

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                rel_str = str(path.relative_to(self.root)).replace("\\", "/")
                scanned_count += 1

                # Check hardcoded secrets
                sec_match = secret_pattern.search(text)
                if sec_match:
                    security_findings.append(
                        {
                            "file": rel_str,
                            "type": "Hardcoded secret pattern detected",
                            "recommendation": "Extract to environment variables (.env)",
                        }
                    )

                # Check var keyword in JS
                if path.suffix in (".js", ".jsx") and var_pattern.search(text):
                    legacy_patterns.append(
                        {
                            "file": rel_str,
                            "type": "Legacy 'var' declarations",
                            "recommendation": "Modernize to const/let",
                        }
                    )

            except Exception:
                continue

        # Check missing infrastructure
        if not (self.root / ".env.example").exists() and (self.root / ".env").exists():
            missing_infra.append("Missing .env.example template file")
        if (
            not (self.root / "Dockerfile").exists()
            and not (self.root / "docker-compose.yml").exists()
        ):
            missing_infra.append("Missing containerization (Dockerfile / docker-compose.yml)")
        if not (self.root / ".github").exists():
            missing_infra.append("Missing CI/CD workflow configuration (.github/workflows)")

        return {
            "outdated_dependencies": outdated_deps,
            "legacy_patterns": legacy_patterns[:15],
            "security_findings": security_findings[:10],
            "missing_infrastructure": missing_infra,
        }

    # ── 7. Reusable Code & Elements ───────────────────────────────────────

    def _identify_reusable_elements(
        self, structure: dict[str, Any], assets: dict[str, Any], tech_stack: dict[str, Any]
    ) -> dict[str, Any]:
        """Index existing business logic, data models, routes, and brand assets to retain."""
        return {
            "reusable_assets_count": assets.get("total_assets", 0),
            "reusable_branding": assets.get("logos", []) + assets.get("icons", []),
            "reusable_configs": structure.get("configs", []),
            "existing_tests": structure.get("tests", []),
            "reusable_models": [
                f
                for f in structure.get("sample_files", [])
                if "model" in f.lower() or "schema" in f.lower()
            ],
            "preservation_policy": "Strict zero-regression policy: existing business logic, routes, and assets remain active and untouched unless specifically upgraded.",
        }

    # ── 8. Phased Modernization Plan ──────────────────────────────────────

    def _build_modernization_plan(
        self, tech_stack: dict[str, Any], debt: dict[str, Any], reusable: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Synthesize a safe, incremental modernization plan."""
        plan: list[dict[str, Any]] = []

        # Phase 1: Security & Secrets Isolation
        plan.append(
            {
                "phase": 1,
                "title": "Security & Credential Hygiene",
                "goal": "Isolate all secrets into .env, ensure .env.example is provisioned, ensure .gitignore guards secrets.",
                "actions": [
                    "Audit codebase for hardcoded credentials",
                    "Ensure .gitignore has .env and .env.local",
                    "Generate .env.example with masked placeholders",
                ],
                "safety_level": "Safe (non-breaking)",
            }
        )

        # Phase 2: Controlled Dependency Upgrade
        outdated = debt.get("outdated_dependencies", [])
        dep_actions = [
            f"Evaluate safe upgrade for {d['package']} ({d.get('reason', '')})"
            for d in outdated[:5]
        ]
        if not dep_actions:
            dep_actions = ["Validate manifest dependency integrity and lockfiles"]

        plan.append(
            {
                "phase": 2,
                "title": "Targeted Dependency Modernization",
                "goal": "Update deprecated packages without breaking backward compatibility.",
                "actions": dep_actions,
                "safety_level": "Tested (verify test suite after changes)",
            }
        )

        # Phase 3: Infrastructure Repair
        missing = debt.get("missing_infrastructure", [])
        infra_actions = missing if missing else ["Verify local build configuration"]
        plan.append(
            {
                "phase": 3,
                "title": "Missing Infrastructure Provisioning",
                "goal": "Equip the repository with modern developer tooling, Docker containerization, and env hygiene.",
                "actions": infra_actions,
                "safety_level": "Additive (no impact on existing runtime)",
            }
        )

        # Phase 4: Feature Extension
        plan.append(
            {
                "phase": 4,
                "title": "Requested Feature Extension (e.g. AI Chatbot)",
                "goal": "Integrate AI services directly into existing backend routes and frontend UI without creating parallel architectures.",
                "actions": [
                    "Inject backend AI service endpoint using existing framework (FastAPI/Express/Flask)",
                    "Add animated Chatbot UI component matching existing design tokens",
                    "Configure LLM credentials (Groq/OpenAI) securely via .env",
                ],
                "safety_level": "Additive (preserves existing routes)",
            }
        )

        # Phase 5: Verification & Zero-Regression Validation
        plan.append(
            {
                "phase": 5,
                "title": "Dual-Track Verification & Final Build",
                "goal": "Run acceptance tests for both legacy features (A, B, C) and new feature (D), ensuring production build passes.",
                "actions": [
                    "Execute unit/integration test suite",
                    "Verify existing routes respond correctly",
                    "Verify new chatbot streaming endpoint",
                    "Validate production bundle build",
                ],
                "safety_level": "Strict validation gate",
            }
        )

        return plan
