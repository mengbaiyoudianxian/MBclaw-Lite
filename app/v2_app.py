"""v2 App factory — original 26 routers + r1 improvements."""
import importlib, os
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app):
    from app.database import init_db
    init_db()
    from app.startup import print_startup_banner
    print_startup_banner()
    yield

def create_app() -> FastAPI:
    app = FastAPI(title="MBclaw v2", version="0.2.0", lifespan=lifespan)
    for rn in ['users','projects','sessions','messages','summaries','dna','keywords',
               'search','memory','action_memories','topics','tools','models','integrations',
               'snapshots','skills','approvals','health','tasks','agent','feedback',
               'collisions','i18n','utopia','llm','providers']:
        mod = importlib.import_module(f'app.routers.{rn}')
        app.include_router(mod.router)
    return app

app = create_app()
