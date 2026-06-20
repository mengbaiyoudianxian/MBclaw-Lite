from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from app.database import init_db
from app.routers import users, projects, sessions, messages, summaries, dna, keywords, search, memory, action_memories, topics, tools, models, integrations, snapshots, skills, approvals, health, tasks, agent, feedback, collisions, i18n, utopia, llm, providers
from app.services.idle_scheduler import start_idle_scheduler, mark_request
from app.services.startup_checker import StartupChecker
from app.middleware.locale import LocaleMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # Project 9: startup checks + self-heal
    checker = StartupChecker()
    checker.self_heal()
    await checker.run_all()
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
app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(agent.router)
app.include_router(feedback.router)
app.include_router(collisions.router)
app.include_router(i18n.router)
app.include_router(utopia.router)
app.include_router(llm.router)
app.include_router(providers.router)

app.add_middleware(LocaleMiddleware)


@app.middleware("http")
async def track_requests(request: Request, call_next):
    mark_request()
    response = await call_next(request)
    return response


@app.get("/")
def root():
    return {"message": "MBclaw-Lite API"}
