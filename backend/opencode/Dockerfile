# AI Solution Builder — OpenCode Sidecar
# Headless OpenCode server that generates MVP prototypes for the backend API.

FROM node:20-slim AS runtime

ENV NODE_ENV=production \
    OPENCODE_ENDPOINT=0.0.0.0 \
    OPENCODE_PORT=4096

WORKDIR /opt/opencode

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Preinstall MVP runtime dependencies so pytest and verification succeed inside the sidecar
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi==0.115.6 \
    "sqlalchemy[asyncio]==2.0.36" \
    aiosqlite \
    pydantic==2.10.4 \
    pydantic-settings==2.7.1 \
    "python-jose[cryptography]" \
    "passlib[bcrypt]" \
    email-validator \
    httpx \
    pytest \
    pytest-asyncio

RUN npm install -g opencode-ai@1.18.32

# Copy OpenCode configuration and custom agents
RUN mkdir -p /root/.config/opencode/agents
COPY config.json /root/.config/opencode/opencode.json
COPY agents/mvp-builder.md /root/.config/opencode/agents/mvp-builder.md

# Workspace root where the backend drops per-solution build directories.
# Mounted as a shared volume so the Python service can read generated files.
RUN mkdir -p /workspace && chmod -R a+rwx /workspace

WORKDIR /workspace
VOLUME ["/workspace"]

EXPOSE 4096

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
  CMD node -e "fetch('http://localhost:4096/global/health').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))" || exit 1

CMD ["opencode", "serve", "--port", "4096", "--hostname", "0.0.0.0"]