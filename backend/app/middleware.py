import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("iddrv.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception:
            duration_s = time.perf_counter() - start
            route = request.scope.get("route")
            route_path = route.path if route else request.url.path
            log_extra = {
                "request_id": request_id,
                "method": request.method,
                "path": route_path,
                "status": 500,
                "duration_ms": round(duration_s * 1000, 3),
            }
            logger.error("request completed", extra=log_extra)
            from .metrics import record_request
            record_request(request.method, 500, duration_s)
            return Response(
                content='{"error":{"code":"internal_error","message":"Internal server error","request_id":"' + request_id + '"}}',
                status_code=500,
                media_type="application/json",
                headers={"X-Request-ID": request_id},
            )

        duration_s = time.perf_counter() - start

        response.headers["X-Request-ID"] = request_id

        from .metrics import record_request
        record_request(request.method, response.status_code, duration_s)

        route = request.scope.get("route")
        route_path = route.path if route else request.url.path

        if request.method == "POST" and route_path.endswith("/investigations"):
            if response.status_code == 403:
                from .metrics import record_investigation_outcome
                record_investigation_outcome("refused")

        status_code = response.status_code
        log_extra = {
            "request_id": request_id,
            "method": request.method,
            "path": route_path,
            "status": status_code,
            "duration_ms": round(duration_s * 1000, 3),
        }

        if status_code >= 500:
            logger.error("request completed", extra=log_extra)
        elif status_code >= 400:
            logger.warning("request completed", extra=log_extra)
        else:
            logger.info("request completed", extra=log_extra)

        return response
