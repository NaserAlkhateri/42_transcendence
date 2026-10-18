from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

from app.api import health, partner
from app.api.v1.router import api_router
from app.core.errors import install_error_handlers
from app.core.security import install_security

API_PREFIX = "/api/v1"

PARTNER_DESCRIPTION = """Read-only access to Sijil vehicle service histories for partners such as insurers and
marketplaces, plus a watchlist for VINs you care about. Sijil is a demo: histories come from approved
workshops and dealerships and are not official records.

**Authentication:** send the key a Sijil platform admin issued you in the `X-API-Key` header. A missing,
unknown or revoked key answers `401`.

**Rate limits:** every response carries `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset`
(seconds). Over the limit you get `429` with `Retry-After`.

**Errors** use one shape: `{"error": {"code": "...", "message": "..."}}`.

Full guide with examples: `doc/PARTNER_API.md` in the repository."""


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sijil API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    install_error_handlers(app)
    install_security(app)
    app.include_router(health.router)
    app.include_router(api_router, prefix=API_PREFIX)
    # Key-authenticated, no cookies: deliberately outside api_router and its CSRF check.
    app.include_router(partner.router, prefix=partner.PARTNER_PREFIX)
    install_partner_docs(app)
    return app


def install_partner_docs(app: FastAPI) -> None:
    """A partner-only spec and Swagger page, so partners see the six endpoints they can call and nothing else."""
    spec: dict = {}

    @app.get(f"{partner.PARTNER_PREFIX}/openapi.json", include_in_schema=False)
    def partner_openapi() -> dict:
        if not spec:
            spec.update(partner_spec(app.openapi()))
        return spec

    @app.get(f"{partner.PARTNER_PREFIX}/docs", include_in_schema=False)
    def partner_docs() -> HTMLResponse:
        return get_swagger_ui_html(openapi_url=f"{partner.PARTNER_PREFIX}/openapi.json", title="Sijil Partner API")


def partner_spec(full: dict) -> dict:
    """The full spec cut down to the partner paths and the schemas they reference."""
    paths = {path: ops for path, ops in full["paths"].items() if path.startswith(partner.PARTNER_PREFIX)}
    all_schemas = full.get("components", {}).get("schemas", {})
    needed: set[str] = set()

    def collect(node: object) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                name = ref.rsplit("/", 1)[1]
                if name not in needed:
                    needed.add(name)
                    collect(all_schemas.get(name))
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)

    collect(paths)
    components = {
        "schemas": {name: all_schemas[name] for name in sorted(needed)},
        "securitySchemes": full.get("components", {}).get("securitySchemes", {}),
    }
    return {
        "openapi": full["openapi"],
        "info": {"title": "Sijil Partner API", "version": "1.0.0", "description": PARTNER_DESCRIPTION},
        "paths": paths,
        "components": components,
    }

app = create_app()
