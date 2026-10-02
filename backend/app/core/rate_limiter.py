import time
import logging
from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from app.core.config import settings
from app.core.cache import cache

logger = logging.getLogger("codesphere.rate_limiter")

class RateLimiter:
    """
    Sliding window rate limiter using Redis with fallback to in-memory store.
    """
    def __init__(self, times: int = 60, seconds: int = 60, key_func: Optional[Callable[[Request], str]] = None):
        self.times = times
        self.seconds = seconds
        self.key_func = key_func or self._default_key_func

    def _default_key_func(self, request: Request) -> str:
        # 1. Prefer Bearer Token if present for session-specific rate limiting
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token:
                return f"token:{abs(hash(token))}"

        # 2. Authenticated user ID/email if present
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "email"):
            return f"user:{user.email}"
        
        # 3. Check forwarded headers for real client IP behind reverse proxy / load balancer
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "127.0.0.1"
        return f"ip:{ip}"

    def __call__(self, request: Request):
        if not settings.RATE_LIMIT_ENABLED:
            return

        identifier = self.key_func(request)
        path = request.url.path
        cache_key = f"rate_limit:{path}:{identifier}"
        now = time.time()

        # In-memory sliding window fallback via cache manager
        current_data = cache.get(cache_key)
        
        if current_data is None:
            # First request in window
            cache.set(cache_key, {"count": 1, "start_time": now}, ttl=self.seconds)
            remaining = self.times - 1
            request.state.rate_limit_remaining = remaining
            return

        count = current_data.get("count", 0)
        start_time = current_data.get("start_time", now)
        elapsed = now - start_time

        if elapsed > self.seconds:
            # Window expired, reset
            cache.set(cache_key, {"count": 1, "start_time": now}, ttl=self.seconds)
            remaining = self.times - 1
            request.state.rate_limit_remaining = remaining
            return

        if count >= self.times:
            retry_after = max(1, int(self.seconds - elapsed))
            logger.warning(f"Rate limit exceeded for {identifier} on {path}. Retry after {retry_after}s.")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.times),
                    "X-RateLimit-Remaining": "0"
                }
            )

        # Increment count
        new_count = count + 1
        ttl_remaining = max(1, int(self.seconds - elapsed))
        cache.set(cache_key, {"count": new_count, "start_time": start_time}, ttl=ttl_remaining)
        request.state.rate_limit_remaining = max(0, self.times - new_count)

# Predefined rate limit tiers
auth_rate_limiter = RateLimiter(times=120, seconds=60)         # 120 requests/min for login/refresh
code_exec_rate_limiter = RateLimiter(times=120, seconds=60)    # 120 submissions/min
ai_rate_limiter = RateLimiter(times=60, seconds=60)            # 60 AI generations/min
api_general_rate_limiter = RateLimiter(times=1000, seconds=60) # 1000 requests/min for standard queries
