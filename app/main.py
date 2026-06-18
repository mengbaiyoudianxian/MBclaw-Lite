from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from app.database import init_db
from app.routers import users, projects, sessions, messages, summaries, dna, keywords, search, memory, action_memories, topics, tools, models, integrations, snapshots, skills, approvals
from app.services.idle_scheduler import start_idle_scheduler, mark_request


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_idle_scheduler(idle_threshold=120, check_interval=30)
    yield


app = FastAPI(title="MBclaw-Lite", version="0.1.0", lifespan=lifespan)

app.include_router(users.router)
app.include_router(projects.router)
app.include_router(sessions.router)
app.include_router(messages.router)
app.include_router(summaries.router)
app.include_router(dna.router)
app.include_router(keywords.router)
app.include_router(search.router)
app.include_router(memory.router)
app.include_router(action_memories.router)
app.include_router(topics.router)
app.include_router(tools.router)
app.include_router(models.router)
app.include_router(integrations.router)
app.include_router(snapshots.router)
app.include_router(skills.router)
app.include_router(approvals.router)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    mark_request()
    response = await call_next(request)
    return response


@app.get("/")
def root():
    return {"message": "MBclaw-Lite API"}
