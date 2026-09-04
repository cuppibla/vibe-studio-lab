"""drive() - the ONLY place a function_response is constructed. Every resume
(machine render, human form, human thumb, time deadline) goes through here,
plus the session helpers the whole lab shares."""
import asyncio

from google.adk import Agent, Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types as gtypes

from . import config


# One session service - and therefore ONE SQLAlchemy async engine - per event
# loop. aiosqlite runs each connection on its own worker thread that calls back
# into the loop that created it, so an engine must never outlive its loop.
_svc_by_loop: dict[asyncio.AbstractEventLoop, DatabaseSessionService] = {}


def svc() -> DatabaseSessionService:
    """The session service for the loop we are on, made once and reused.

    run() below disposes it before the loop closes. Called with no loop running
    (a caller driving its own asyncio), you get a fresh one and you own it."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return DatabaseSessionService(db_url=config.DB_URL)
    service = _svc_by_loop.get(loop)
    if service is None:
        service = _svc_by_loop[loop] = DatabaseSessionService(db_url=config.DB_URL)
    return service


def runner_for(node) -> Runner:
    kw = {"agent": node} if isinstance(node, Agent) else {"node": node}
    return Runner(app_name=config.APP, session_service=svc(),
                  auto_create_session=True, **kw)


async def say(node, session_id: str, text: str, user_id: str = config.USER) -> str | None:
    """Plain text turn; returns the model's last text."""
    return await _drive(node, session_id, [gtypes.Part(text=text)], user_id)


async def answer(node, session_id: str, call_id: str, name: str,
                 response: dict, user_id: str = config.USER) -> str | None:
    """Deliver one result to a pending long-running call, by id."""
    part = gtypes.Part(function_response=gtypes.FunctionResponse(
        id=call_id, name=name, response=response))
    return await _drive(node, session_id, [part], user_id)


async def _drive(node, session_id: str, parts,
                 user_id: str = config.USER) -> str | None:
    texts = []
    async for ev in runner_for(node).run_async(
            user_id=user_id, session_id=session_id,
            new_message=gtypes.Content(role="user", parts=parts)):
        msg = getattr(ev, "message", None) or getattr(ev, "content", None)
        for p in (getattr(msg, "parts", None) or []):
            if getattr(p, "text", None):
                texts.append(p.text)
    return texts[-1] if texts else None


async def pending(session_id: str,
                  user_id: str = config.USER) -> list[tuple[str, str, dict]]:
    """Open calls = every long-running id whose LATEST response still says pending.
    RequestInput interrupts arrive with their question in the CALL args, so if no
    response exists yet we surface the args as the payload."""
    s = await svc().get_session(app_name=config.APP, user_id=user_id,
                                session_id=session_id)
    if s is None:
        return []
    lr, calls, latest = set(), {}, {}
    for ev in s.events:
        if getattr(ev, "long_running_tool_ids", None):
            lr |= set(ev.long_running_tool_ids)
        for f in ev.get_function_calls() or []:
            calls[f.id] = (f.name, f.args or {})
        for r in ev.get_function_responses() or []:
            latest[r.id] = (r.name, r.response)
    out = []
    for cid in lr:
        if cid in latest:
            name, resp = latest[cid]
            if isinstance(resp, dict) and resp.get("status") == "pending":
                out.append((cid, name, resp))
        elif cid in calls:                       # asked, never answered (RequestInput)
            name, args = calls[cid]
            out.append((cid, name, {"status": "pending", **args}))
    return out


async def session_state(session_id: str) -> dict:
    s = await svc().get_session(app_name=config.APP, user_id=config.USER,
                                session_id=session_id)
    return dict(s.state) if s else {}


async def ensure_user_state(session_id: str) -> dict:
    """Read state for a session that may not exist yet - creating it attaches
    the user's cross-session `user:` keys (that's the point of the prefix)."""
    service = svc()
    s = await service.get_session(app_name=config.APP, user_id=config.USER,
                                  session_id=session_id)
    if s is None:
        await service.create_session(app_name=config.APP, user_id=config.USER,
                                     session_id=session_id)
        s = await service.get_session(app_name=config.APP, user_id=config.USER,
                                      session_id=session_id)
    return dict(s.state) if s else {}


def run(coro):
    """Sync bridge - Studio's page handlers and every CLI verb call this.

    asyncio.run() builds a FRESH loop each time and closes it on the way out,
    so the engine svc() made inside must be disposed before that happens.
    Without this, aiosqlite's worker threads outlive their loop and every later
    callback raises `RuntimeError: Event loop is closed` - one more leaked pool
    per page poll."""
    async def _disposing():
        try:
            return await coro
        finally:
            service = _svc_by_loop.pop(asyncio.get_running_loop(), None)
            if service is not None:
                await service.close()   # DatabaseSessionService.close() -> db_engine.dispose()
    return asyncio.run(_disposing())
