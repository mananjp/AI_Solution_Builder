"""Seed a demo user + organization + workspace for hands-on testing.

Usage (from backend/):
    python scripts/seed_demo.py

Creates (or reuses) the demo account and prints its login credentials.
"""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.database import Base, async_session_factory
from app.core.security import hash_password
from app.models.credit import Plan
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace

DEMO_EMAIL = "demo@aibuilder.example"
DEMO_PASSWORD = "DemoPass123!"


async def main() -> int:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.begin() as conn:
        from sqlalchemy import text

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    async with async_session_factory() as db:
        org = (
            await db.execute(select(Organization).where(Organization.name == "Demo Org"))
        ).scalar_one_or_none()
        user = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()

        if user is None:
            if org is None:
                plan = (
                    await db.execute(select(Plan).where(Plan.name == "free"))
                ).scalar_one_or_none()
                if plan is None:
                    plan = Plan(
                        name="free", monthly_credits=200, max_workable_systems=1, price_usd=0
                    )
                    db.add(plan)
                    await db.flush()
                org = Organization(name="Demo Org", plan_id=plan.id, credits_remaining=200)
                db.add(org)
                await db.flush()
            user = User(
                email=DEMO_EMAIL,
                full_name="Demo User",
                hashed_password=hash_password(DEMO_PASSWORD),
                role="admin",
                org_id=org.id,
            )
            db.add(user)
            await db.flush()

        if org is not None:
            ws = (
                await db.execute(
                    select(Workspace).where(
                        Workspace.org_id == org.id, Workspace.name == "Demo Workspace"
                    )
                )
            ).scalar_one_or_none()
            if ws is None:
                ws = Workspace(
                    org_id=org.id,
                    name="Demo Workspace",
                    description="Pre-created workspace for trying the MVP builder",
                )
                db.add(ws)
        await db.commit()

        print("Demo user ready:")
        print(f"  email    : {DEMO_EMAIL}")
        print(f"  password : {DEMO_PASSWORD}")
        if org is not None and ws is not None:
            print(f"  org      : {org.name} ({org.id})")
            print(f"  workspace: {ws.name} ({ws.id})")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
