# Threat Scanning Architecture & Operations Guide (SEC-SCAN-001)

AI Solution Builder implements a multi-layer threat defense architecture protecting both **Ingress** (*outside-in*) and **Egress** (*inside-out*) resources.

---

## 1. Multi-Layer Defense Overview

```
                      Incoming / Outgoing Asset
                                  │
                                  ▼
                     [ Orchestrator & Cache ]
                     (7-day Redis sha256 cache)
                                  │
             ┌────────────────────┼────────────────────┐
             ▼                    ▼                    ▼
     [ Layer 0: Local ]   [ Layer 1: ClamAV ]  [ Layer 2: VirusTotal ]
     • Always on (sync)   • Optional daemon    • Opt-in (dev only)
     • Sub-millisecond    • Unlimited scans    • 4 RPM / 500 Daily
     • Magic / Macro /    • Raw TCP zINSTREAM  • ToS gated
       Archive Bombs      • 0 new pip deps     • Strict privacy hash-mode
             │                    │                    │
             └────────────────────┼────────────────────┘
                                  ▼
                         [ Verdict Resolver ]
                  Worst: MALICIOUS > SUSPICIOUS > ...
                                  │
                                  ▼
                        [ Policy Enforcement ]
                    threshold: suspicious | malicious
                    fail_mode: allow | quarantine | block
```

### Layer Comparison

| Layer | Type | Availability | Latency | Focus |
|---|---|---|---|---|
| **Layer 0: Local Rules** | Offline, pure Python | Always On (production backbone) | <1ms | File magic, polyglots, extension spoofing, EICAR canary, OOXML macros, zip bombs & zip slips |
| **Layer 1: ClamAV** | Local daemon | Optional (`CLAMAV_ENABLED=true`) | ~10-50ms | Signature-based malware scanning over raw TCP `zINSTREAM` without external pip dependencies |
| **Layer 2: VirusTotal** | Cloud API (v3) | Opt-in (`VIRUSTOTAL_ACK_TOS=true`) | 200-800ms | 70+ vendor cloud intelligence; limited to 4 req/min; strictly gated behind non-commercial terms |

---

## 2. Protected Ingress & Egress Hooks

### Ingress (Outside to In)
1. **URL Ingestion** (`/api/v1/upload/url`): scanned before web extraction.
2. **Document Uploads** (`/api/v1/upload/document`): PDF, DOCX, CSV, Excel scanned before PyMuPDF or pandas parser execution.
3. **Audio Notes** (`/api/v1/upload/audio`): scanned before shipping audio to Groq Whisper transcription.
4. **UI Wireframe/Screenshots** (`/api/v1/upload/image`): scanned before computer vision context extraction.
5. **System Importer** (`/api/v1/upload/system`): GitHub repository URL scanned before fetching README.
6. **Uploaded Codebase ZIPs** (`/api/v1/legacy-repo/analyze-upload`): synchronous `guard_archive` inspection followed by multi-layer scan before safe extraction.
7. **GitHub Archive Zipballs** (`/api/v1/legacy-repo/analyze`): scanned before safe workspace extraction.

### Egress (Inside to Out)
8. **Deployable Solution ZIPs** (`/api/v1/export/{id}/zip`): scanned prior to HTTP streaming response when `SCAN_GENERATED_ARTIFACTS=true`.
9. **Generated MVP Code Packages** (`mvp_builder.package_build`): archive structure verified prior to storage upload.
10. **One-Click Deployments** (`deployer.py`): safe archive extraction prevents path traversal during repository pushes.

---

## 3. Configuration Reference

```ini
# Core Threat Scanner
SECURITY_SCAN_ENABLED=true
SECURITY_SCAN_BLOCK_THRESHOLD=suspicious    # malicious | suspicious
SECURITY_SCAN_FAIL_UNAVAILABLE_MODE=allow  # allow | quarantine | block
SECURITY_SCAN_SOURCES=                      # comma-separated globs, or empty for all
SECURITY_CACHE_TTL=604800                   # 7 days

# Layer 1: ClamAV Daemon
CLAMAV_ENABLED=false
CLAMAV_HOST=clamav
CLAMAV_PORT=3310
CLAMAV_TIMEOUT=5.0

# Layer 2: VirusTotal API (Community Tier)
VIRUSTOTAL_ENABLED=false
VIRUSTOTAL_ACK_TOS=false
VIRUSTOTAL_API_KEY=
VIRUSTOTAL_MIN_DETECTIONS=3
VIRUSTOTAL_RPM=4
VIRUSTOTAL_DAILY=500

# Archive Safety Caps
ARCHIVE_MAX_ENTRIES=10000
ARCHIVE_MAX_UNCOMPRESSED_BYTES=524288000   # 500 MB
ARCHIVE_MAX_RATIO=100
ARCHIVE_MAX_NESTED_DEPTH=2
SCAN_GENERATED_ARTIFACTS=false
```

---

## 4. Error Responses

When an asset is blocked, the API responds with HTTP 422 in the unified error envelope:

```json
{
  "error": {
    "code": "SECURITY_SCAN_BLOCKED",
    "message": "Asset blocked by threat scanner: detected as malicious",
    "details": ["eicar_test_file"]
  }
}
```

For zip bombs or path traversal violations:

```json
{
  "error": {
    "code": "SECURITY_ARCHIVE_REJECTED",
    "message": "Archive member contains directory traversal segment: '../evil.sh'",
    "details": ["archive_traversal"]
  }
}
```
