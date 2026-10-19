"""Local, deliberately constrained prototype service."""
from __future__ import annotations

from importlib.resources import files
import json
import os
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import context, providers, store
from .claims import STATUSES, TransitionError
from .store import ForgetImpactChanged, Vault


class NoteIn(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    sensitivity: Literal["private", "sensitive"] = "private"


class ClaimIn(BaseModel):
    # extra="forbid": a client-supplied `status` is rejected, not silently ignored.
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=8)
    # No `origin` field: provenance is assigned by the server, never by the browser.


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]
    note: str | None = Field(default=None, max_length=500)
    # Required compare-and-set: the decision applies only if the claim is still in the state
    # the human was looking at; otherwise 409, so two conflicting decisions never both succeed.
    expected_status: Literal[STATUSES]


class SupersedeIn(DecisionIn):
    text: str = Field(min_length=1, max_length=2000)
    source_ids: list[str] = Field(min_length=1, max_length=8)


class RestoreIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_trusted_restore: Literal[True]
    backup: dict


class CompileIn(BaseModel):
    # extra="forbid": a client cannot smuggle context, roles, authority or messages into a request.
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=2000)
    provider: Literal["local", "kimi", "openai"] = "local"
    # Pinned evidence: high-priority candidates that still pass every compiler policy.
    source_ids: list[str] = Field(default_factory=list, max_length=8)


class AskIn(CompileIn):
    approve_cloud_disclosure: bool = False
    # The token of the previewed bundle. Required for cloud; checked when given for local.
    context_token: str | None = Field(default=None, max_length=128)


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Sovereign OS — Prototype", docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    vault = Vault(db_path or os.getenv("SOVEREIGN_DB_PATH", "./data/sovereign.db"))
    app.state.vault = vault

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        # Not a full local authentication system. Avoid casual browser-origin requests.
        origin = request.headers.get("origin", "")
        if origin and origin not in {"http://127.0.0.1:8765", "http://localhost:8765", "http://testserver"}:
            return JSONResponse({"detail": "Cross-origin request denied"}, status_code=403)
        if request.url.path.startswith("/api/") and request.method in ("POST", "PATCH", "DELETE"):
            if request.method != "DELETE" and not request.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse({"detail": "JSON only"}, status_code=415)
        if request.url.path in ("/api/import", "/api/restore"):
            # One explicit size policy for backups (export refuses to produce anything larger).
            length = request.headers.get("content-length", "")
            if not length.isdigit():
                return JSONResponse({"detail": "Content-Length required"}, status_code=411)
            if int(length) > store.MAX_BACKUP_BYTES + 4096:   # room for the restore wrapper only
                return JSONResponse({"detail": "Backup exceeds the V0 single-file size limit"}, status_code=413)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    def home():
        return (files("sovereign").joinpath("static/index.html")).read_text(encoding="utf-8")

    @app.get("/ui.css")
    def css():
        from fastapi.responses import Response
        return Response((files("sovereign").joinpath("static/style.css")).read_text(encoding="utf-8"), media_type="text/css")

    @app.get("/ui.js")
    def js():
        from fastapi.responses import Response
        return Response((files("sovereign").joinpath("static/app.js")).read_text(encoding="utf-8"), media_type="application/javascript")

    @app.get("/api/status")
    def status():
        return {"mode": "prototype", "local": True, "providers": providers.available(),
                "warning": "Synthetic/non-sensitive data only. No at-rest vault encryption or user authentication."}

    @app.get("/api/memories")
    def list_memories(q: str = ""):
        return {"records": vault.search(q, 60)}

    @app.post("/api/memories", status_code=201)
    def add_memory(note: NoteIn):
        try:
            return vault.add(note.content, note.sensitivity)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    # `:path` because ADR-0002 accepted record ids of any text, including "/"; such a legacy record
    # must still be previewable, correctable and above all forgettable.
    @app.post("/api/memories/{record_id:path}/correct")
    def correct(record_id: str, note: NoteIn):
        try:
            return vault.add(note.content, note.sensitivity, supersedes_id=record_id)
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @app.get("/api/memories/{record_id:path}/forget-preview")
    def forget_preview(record_id: str):
        # Server-authoritative: exactly what DELETE would remove now (same plan, same code path).
        plan = vault.forget_preview(record_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return plan

    @app.delete("/api/memories/{record_id:path}")
    def remove(record_id: str, expected_impact: str | None = None):
        # Forget: the record, its earlier revisions and every claim derived from them. With the
        # preview's token the request fails (409) if the effect changed since it was confirmed.
        try:
            result = vault.delete(record_id, expected_impact)
        except ForgetImpactChanged as e:
            raise HTTPException(status_code=409, detail=str(e))
        if result is None:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"removed": True, **result,
                "note": "Forgotten from active SQLite rows with dependent claims; backups/forensic copies not covered."}

    def claim_errors(action):
        try:
            return action()
        except KeyError as e:
            raise HTTPException(status_code=404, detail=str(e.args[0]))
        except TransitionError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=409, detail=f"Rejected by vault integrity rules: {e}")
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @app.get("/api/claims")
    def list_claims(status: Literal[STATUSES] | None = None, cursor: str | None = None,
                    limit: int = Query(default=100, ge=1, le=store.MAX_PAGE)):
        # Newest first; follow `next_cursor` until it is null to reach every claim.
        try:
            return vault.claims_page(status, limit, cursor)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

    @app.post("/api/claims", status_code=201)
    def add_claim(claim: ClaimIn):
        return claim_errors(lambda: vault.add_claim(claim.text, claim.source_ids, "human"))

    # Status changes are explicit local human actions; no model code path calls these.
    # `:path`: a trusted restore accepts any 1-200 character claim id, so every listed claim stays actionable.
    @app.post("/api/claims/{claim_id:path}/approve")
    def approve_claim(claim_id: str, body: DecisionIn):
        return claim_errors(lambda: vault.transition_claim(claim_id, "approved", body.note, body.expected_status))

    @app.post("/api/claims/{claim_id:path}/reject")
    def reject_claim(claim_id: str, body: DecisionIn):
        return claim_errors(lambda: vault.transition_claim(claim_id, "rejected", body.note, body.expected_status))

    @app.post("/api/claims/{claim_id:path}/contest")
    def contest_claim(claim_id: str, body: DecisionIn):
        return claim_errors(lambda: vault.transition_claim(claim_id, "contested", body.note, body.expected_status))

    @app.post("/api/claims/{claim_id:path}/supersede")
    def supersede_claim(claim_id: str, body: SupersedeIn):
        return claim_errors(lambda: vault.supersede_claim(claim_id, body.text, body.source_ids, body.note, body.expected_status))

    @app.delete("/api/claims/{claim_id:path}")
    def remove_claim(claim_id: str):
        if not vault.delete_claim(claim_id):
            raise HTTPException(status_code=404, detail="Claim not found")
        return {"removed": True}

    @app.get("/api/export")
    def export():
        from fastapi.responses import Response
        body = json.dumps(vault.export(), indent=2)
        if len(body.encode("utf-8")) > store.MAX_BACKUP_BYTES:
            # Never hand out a backup that import/restore would refuse.
            raise HTTPException(status_code=413, detail="Vault exceeds the V0 single-file backup limit; nothing was exported.")
        return Response(body, media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=sovereign-export.json", "Cache-Control": "no-store"})

    @app.post("/api/import")
    def import_data(payload: dict):
        # Untrusted: evidence and *proposed* claims only; never authority, never local deletions.
        try:
            return vault.import_untrusted(payload)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=422, detail=f"Import rejected by vault integrity rules: {exc}")

    @app.post("/api/restore")
    def restore_backup(body: RestoreIn):
        # Trusted restore of the user's own Sovereign backup: preserves authority, applies tombstones.
        try:
            return vault.restore_trusted(body.backup)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=422, detail=f"Backup rejected by vault integrity rules: {exc}")

    def compiled(body: CompileIn, previewed: bool = False):
        try:
            return context.compile_context(vault, body.question, body.provider, body.source_ids)
        except context.PinnedSourceForgotten as exc:
            # After a preview, a pin forgotten since then means the approved plan no longer holds.
            raise HTTPException(409 if previewed else 422, context.CHANGED if previewed else str(exc))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.post("/api/context/compile")
    def compile_context(body: CompileIn):
        # Read-only preview of exactly what a request would use and, for cloud, transmit (ADR-0004).
        return compiled(body).describe()

    @app.post("/api/ask")
    def ask(question: AskIn):
        # Every model-bound byte comes from a bundle compiled now, in one read snapshot, by the same
        # code as the preview; nothing here reads the vault for a provider or writes to it.
        bundle = compiled(question, previewed=question.context_token is not None)
        evidence = [{"id": i.candidate.id, "content": i.candidate.content, "created_at": i.candidate.created_at}
                    for i in bundle.included if i.role == "evidence"]
        if bundle.boundary == "local":
            if question.context_token is not None and question.context_token != bundle.context_token:
                raise HTTPException(409, context.CHANGED)
            answer = ("Local evidence only — no model was called. These are the approved memories and source records "
                      "the Context Compiler selected for this question; no conclusions were inferred."
                      if bundle.included else
                      "No approved memory or source record in your vault matched this question. Rephrase it, or "
                      "select records in your library to pin them.")
            return {"answer": answer, "provider": "local", "sources": evidence, "cloud_disclosure": False,
                    "context": bundle.describe(), "receipt": bundle.receipt(transmitted=False).describe()}

        # Crucially, cloud approval is checked by the server, not only the UI, and it approves one exact plan.
        if not question.approve_cloud_disclosure:
            raise HTTPException(403, "Cloud transmission requires an explicit approval for this request.")
        if bundle.blocked:
            raise HTTPException(403, bundle.blocked["detail"])
        ready = {p["id"]: p["ready"] for p in providers.available()}
        if not ready.get(question.provider):
            raise HTTPException(503, "Provider not configured. Set the appropriate API key and model in environment.")
        if not question.context_token:
            raise HTTPException(428, "Preview the context first (POST /api/context/compile) and approve its exact "
                                     "plan: context_token is required for cloud requests.")
        if question.context_token != bundle.context_token:
            raise HTTPException(409, context.CHANGED)   # no provider call: the plan the human approved no longer holds
        try:
            # The provider receives the approved bundle's messages and nothing else; its reply is returned as text
            # and never written to memory.
            answer = providers.generate(question.provider, [dict(m) for m in bundle.messages])
        except Exception as exc:
            # Never expose provider exceptions, request bodies, or secret-bearing error objects to browser.
            raise HTTPException(502, "The model request failed. Check server logs/configuration.") from None
        return {"answer": answer, "provider": question.provider, "sources": evidence, "cloud_disclosure": True,
                "context": bundle.describe(), "receipt": bundle.receipt(transmitted=True).describe(),
                "disclosed": {"provider": question.provider, "question_included": True,
                              "items": [{"id": i.candidate.id, "type": i.candidate.type, "role": i.role}
                                        for i in bundle.included]}}

    return app

app = create_app()
