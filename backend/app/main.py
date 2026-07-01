from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, artists, auth, feed, friends, genres, invites, users

# Schema is managed by Alembic migrations (`alembic upgrade head`), not create_all.

app = FastAPI(title="Concert With Friends", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    # Token-based auth (Bearer header), no cookies — credentials must stay off
    # because "*" origins + credentials is rejected by the CORS spec.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(artists.router)
app.include_router(genres.router)
app.include_router(feed.router)
app.include_router(friends.router)
app.include_router(invites.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
