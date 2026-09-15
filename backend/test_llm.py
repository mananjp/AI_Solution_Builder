import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from app.core.config import settings
print("LLM_PROVIDER:", repr(settings.LLM_PROVIDER))
print("GROQ_API_KEY:", repr(settings.GROQ_API_KEY[:20] if settings.GROQ_API_KEY else ""))
print("APP_ENV:", repr(settings.APP_ENV))

# Also check the .env file directly
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.strip().startswith("GROQ_API_KEY"):
                print("FROM FILE:", line.strip()[:40])
            if line.strip().startswith("LLM_PROVIDER"):
                print("FROM FILE:", line.strip())
