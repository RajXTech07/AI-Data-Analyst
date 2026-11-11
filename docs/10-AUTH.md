# 10 — Authentication and Authorization

## 1. Scope

MVP: email + password, JWT access tokens, refresh token in an httpOnly cookie, strict per-user data isolation. A **demo mode** (no login, session-scoped data, auto-expiry) is acceptable if time runs short.

## 2. Flow

```
Register → hash password (argon2id) → store user
Login    → verify → issue access token (15 min) + refresh cookie (7 days)
Request  → Authorization: Bearer <access>  → get_current_user dependency
Expired  → POST /auth/refresh (cookie) → new access token (rotate refresh)
Logout   → clear cookie, revoke refresh token
```

## 3. Passwords
- Hash with **argon2id** (`argon2-cffi`).
- Minimum length 10; reject very common passwords.
- Same error message for wrong email and wrong password.
- Rate limit login: 5 attempts / 15 min / IP+email.

## 4. Tokens
- Access token: JWT (HS256 for MVP; RS256 if you add services), claims `sub`, `exp`, `iat`, `jti`.
- Refresh token: random opaque string, stored **hashed** in a `refresh_tokens` table (`id, user_id, token_hash, expires_at, revoked_at`), rotated on every use. Reuse of a revoked token revokes the whole family.
- Cookie flags: `HttpOnly; Secure; SameSite=Lax; Path=/api/v1/auth`.
- Keep the access token in memory on the client, not in localStorage.

## 5. FastAPI dependency
```python
async def get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid token")
    user = await db.get(User, payload["sub"])
    if not user:
        raise HTTPException(401, "Invalid token")
    return user
```

## 6. Authorization (ownership)
Every query touching user data includes the owner:
```python
stmt = select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == user.id)
```
- Not found or not yours → **404**.
- Analyses, findings, charts, messages, reports inherit access through `analyses.user_id`.
- Tool execution loads the DataFrame only after the ownership check.
- Add tests that user B cannot read, analyse, delete or download user A's data.

## 7. SSE and downloads
EventSource cannot set headers. Options: fetch-based SSE client (supports headers), or short-lived signed URL token (60 s, single analysis) as a query parameter. Never put the long-lived access token in a URL.

## 8. CORS and CSRF
- CORS allow-list: only `WEB_ORIGIN`, credentials enabled.
- Bearer tokens in headers are not CSRF-prone; the refresh endpoint is, so require `SameSite` cookie and check the `Origin` header.

## 9. Account endpoints (later)
Email verification, password reset (signed single-use token, 30 min), delete account (cascades all data).

## 10. Optional: OAuth
Google sign-in via OAuth2/OIDC (Authlib). Not needed for MVP.

## 11. Checklist
- [ ] argon2id hashing
- [ ] Short-lived access token, rotating refresh
- [ ] Ownership filter on every query
- [ ] Rate limits on auth routes
- [ ] No tokens in localStorage or URLs
- [ ] Secrets only in env
- [ ] Cross-user access tests
