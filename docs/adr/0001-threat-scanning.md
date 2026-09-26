# ADR 0001: Multi-Layer Threat Scanning & VirusTotal Guardrails

- **Status**: Accepted
- **Date**: 2026-09-26
- **Ticket**: `SEC-SCAN-001`
- **Deciders**: Architecture & Security Team

---

## Context

AI Solution Builder ingests external user assets (PDF, DOCX, CSV/XLSX, voice notes, UI wireframe images, public GitHub URLs, and uploaded ZIP archives) and generates deployable software architectures and MVP packages.

We considered integrating the VirusTotal API to enforce security across these assets. However:
1. **Commercial Terms of Service**: The free VirusTotal Community API strictly forbids use in commercial products/services and throttles to 4 requests/minute and 500 requests/day.
2. **Confidentiality & Privacy**: Raw files submitted to public VirusTotal are distributed to threat intelligence subscribers worldwide, creating an unacceptable intellectual property leak for proprietary customer code and confidential business documents.
3. **Latency**: Synchronous multi-vendor cloud AV scans take 30–120 seconds, causing gateway timeouts on ingestion endpoints.
4. **Code Generation Blind Spots**: VirusTotal detects compiled viruses and trojans, but is ineffective at detecting hardcoded API keys, OWASP vulnerabilities (SQLi, XSS), or vulnerable npm/PyPI dependencies in LLM-generated source code.

---

## Decision

We have adopted a **three-layer defense-in-depth architecture**:

1. **Layer 0: Local Offline Rules (Always On, Production Backbone)**:
   - Synchronous, sub-millisecond, pure Python without C-extension dependencies.
   - Inspects binary magic numbers (PE, ELF, Mach-O, DEX, WASM), detects polyglot/extension spoofing, identifies OLE2 legacy macro carriers, scans for OOXML VBA macros inside ZIP structures, enforces denylists, and validates against EICAR canary signatures.
2. **Archive Hardening (`guard_archive` and `safe_extract_zip`)**:
   - Central directory header inspection before decompressing any byte.
   - Strictly enforces uncompressed size limits (zip-bomb guard), compression ratio caps, entry count caps, nesting depth limits, and eliminates path traversal (Zip Slip) across all 5 extraction sites.
3. **Layer 1: ClamAV Daemon (Optional, Unlimited)**:
   - Communicates with a local `clamd` container via raw TCP `zINSTREAM\0` protocol.
   - Requires zero new Python dependencies.
4. **Layer 2: VirusTotal API (Opt-in, Development Signal Only)**:
   - Disabled by default. Boot requires explicit `VIRUSTOTAL_ACK_TOS=true` acknowledging non-commercial terms.
   - Enforces hash-first lookups and unpadded Base64 URL queries with a 7-day Redis cache.
   - Throttled by a Redis token bucket (4 RPM / 500 daily).
   - Only allowlisted fields are retained.

---

## Consequences

### Positive
- Production security is completely independent of external vendor APIs and rate limits.
- Zero data leakage: proprietary customer code and confidential spreadsheets are never uploaded to public threat feeds.
- Zero new pip dependencies added to `requirements.txt`.
- Five legacy `extractall` call sites are hardened against zip slip and zip bombs.
- Complete auditability via `ScanRecord` model and admin governance APIs.

### Limitations & Trade-offs
- VirusTotal is an optional signal, not a production dependency.
- LLM-generated source code text must be audited at the archive boundary; static code analysis (SAST) and secret scanning remain complementary practices.
