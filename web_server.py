"""HTTP-сервер для Telegram Mini App и API событий."""

from __future__ import annotations

from pathlib import Path

from aiohttp import web

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"


def create_webapp(db, *, cors: bool = True) -> web.Application:
    app = web.Application()

    async def api_events(_request: web.Request) -> web.Response:
        events = await db.get_upcoming_events(limit=10)
        payload = []
        for ev in events:
            filled = await db.confirmed_count(int(ev["id"]))
            payload.append(
                {
                    "id": int(ev["id"]),
                    "title": ev["title"],
                    "event_type": ev["event_type"],
                    "event_date": ev["event_date"],
                    "event_time": ev["event_time"],
                    "filled": filled,
                    "max_players": int(ev["max_players"]),
                }
            )
        return web.json_response(payload)

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    @web.middleware
    async def cors_middleware(request: web.Request, handler):
        if request.method == "OPTIONS":
            resp = web.Response()
        else:
            resp = await handler(request)
        if cors:
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        return resp

    app.middlewares.append(cors_middleware)
    app.router.add_get("/api/events", api_events)
    app.router.add_get("/healthz", health)
    app.router.add_get("/", lambda _r: web.FileResponse(WEBAPP_DIR / "index.html"))
    app.router.add_static("/static/", WEBAPP_DIR, show_index=False)
    return app


async def start_webapp_server(db, *, host: str = "0.0.0.0", port: int = 8080) -> web.AppRunner:
    app = create_webapp(db)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    return runner
