# Authentication Implementation — Task Checklist

## Stage 1 — Auth Foundation (Backend Core)
- [ ] Add `PyJWT`, `bcrypt`, `Flask-Limiter` to [requirements.txt](file:///v:/PlayGround/ML-Deployment-Platform/requirements.txt)
- [ ] Add `JWT_SECRET_KEY`, `JWT_EXPIRY_HOURS` to [config.py](file:///v:/PlayGround/ML-Deployment-Platform/backend/config.py)
- [ ] Add `User` model to [backend/database/models.py](file:///v:/PlayGround/ML-Deployment-Platform/backend/database/models.py)
- [ ] Create Alembic migration for `users` table
- [ ] Create `backend/services/auth_service.py` (register, login, token logic)
- [ ] Create `backend/core/auth_middleware.py` (`@require_auth`, `@require_admin`)
- [ ] Create `backend/api/auth.py` (POST /register, POST /login, GET /me)
- [ ] Register `auth_bp` Blueprint in [app.py](file:///v:/PlayGround/ML-Deployment-Platform/backend/app.py)
- [ ] Protect SocketIO [connect](file:///v:/PlayGround/ML-Deployment-Platform/frontend/src/services/socket.js#16-54) with JWT token check

## Stage 2 — Ownership & Authorization
- [ ] Create Alembic migration to add FK constraints on `applications.created_by_user_id` and `deployments.triggered_by_user_id`
- [ ] Create `backend/services/user_repository.py` (UserRepository class)
- [ ] Update `DeploymentRepository.list_all()` to filter by `user_id` for non-admins
- [ ] Update `ApplicationRepository.list_by_tenant()` to filter by `user_id` for non-admins
- [ ] Update deployment creation to store `triggered_by_user_id = current_user.id`
- [ ] Update application creation to store `created_by_user_id = current_user.id`
- [ ] Add `@require_auth` to all existing API endpoints
- [ ] Add `@require_admin` to instance terminate and stats endpoints

## Stage 3 — Frontend Auth Integration
- [ ] Create `frontend/src/contexts/AuthContext.jsx` (token state, login, logout)
- [ ] Create `frontend/src/pages/Login.jsx`
- [ ] Create `frontend/src/pages/Register.jsx`
- [ ] Add `login()` and `register()` methods to [api.js](file:///v:/PlayGround/ML-Deployment-Platform/frontend/src/services/api.js)
- [ ] Add JWT Authorization header interceptor to `ApiService.request()`
- [ ] Update [socket.js](file:///v:/PlayGround/ML-Deployment-Platform/frontend/src/services/socket.js) to pass token in connection query
- [ ] Create `frontend/src/components/ProtectedRoute.jsx`
- [ ] Refactor [App.jsx](file:///v:/PlayGround/ML-Deployment-Platform/frontend/src/App.jsx) — separate auth layout vs main layout
- [ ] Add `/login`, `/register` routes and protect all other routes

## Stage 4 — Security Hardening
- [ ] Add `Flask-Limiter` rate limiting to `/api/auth/login` (5/minute) and `/api/auth/register` (3/minute)
- [ ] Add password strength validation in `auth_service.py` (8+ chars, uppercase, number, special char)
- [ ] Add input validation for email format and required fields in `auth.py`
- [ ] Add frontend token expiry detection — redirect to `/login` on 401 response

## Stage 5 — Admin Platform Controls
- [ ] Create `backend/api/admin.py` (GET /api/admin/users, /api/admin/deployments, /api/admin/platform-stats)
- [ ] Register `admin_bp` Blueprint in [app.py](file:///v:/PlayGround/ML-Deployment-Platform/backend/app.py)
- [ ] Create `frontend/src/pages/admin/AdminUsers.jsx`
- [ ] Create `frontend/src/pages/admin/AdminDeployments.jsx`
- [ ] Add `/admin/*` routes (admin-only protected) to [App.jsx](file:///v:/PlayGround/ML-Deployment-Platform/frontend/src/App.jsx)
- [ ] Add Admin section to `Sidebar.jsx` (visible only for admin role)
