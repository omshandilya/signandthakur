# CLAUDE.md - CA Firm Client Management Portal Guidelines

## Project Overview
A web application for a Chartered Accountant (CA) firm to manage clients, service catalogs, service requests, and confirmation documents. Built with Django (MVT), Bootstrap 5, and PostgreSQL in production (SQLite locally).

---

## Core Rules & Constraints

1. **User Roles & Hierarchy**
   - Exactly three roles: `CLIENT`, `EMPLOYEE`, `ADMIN` (the CA / firm owner).
   - Use custom user model `accounts.User` inheriting from `AbstractUser` with fields:
     - `role`: Choice field (`CLIENT`, `EMPLOYEE`, `ADMIN`), default `CLIENT`.
     - `phone`: CharField for contact number.
     - `date_of_birth`: DateField (optional/required as specified per profile).
   - `AUTH_USER_MODEL = 'accounts.User'` is configured from Day One before any migrations are run.

2. **User Registration & Lifecycle**
   - **CLIENT**: Only clients self-register via the public sign-up page.
   - **EMPLOYEE**: Employees CANNOT self-register; they are created and managed strictly by the `ADMIN`.
   - **ADMIN**: Admin account is provisioned via `python manage.py createsuperuser` with role set to `ADMIN`.

3. **Document & Upload Rules**
   - **Clients NEVER upload anything**. No client-facing upload forms or endpoints.
   - **Only Employees (or Admin) upload confirmation documents** upon completing or acknowledging a client's service request.
   - Files are stored securely and served only to authorized users after checking role/ownership.

4. **Notifications & Asynchronous Tasks**
   - **NO email notifications** and **NO Celery / message brokers**.
   - The application is purely synchronous. Users refresh the site to view status updates, assignments, and documents.

5. **Architecture & Service Layer**
   - **Thin Views**: Views handle HTTP requests, form validation, and template response rendering only.
   - **Business Logic in `services.py`**: All domain logic, status transitions, role validations, assignments, and file attachments must reside in `services.py` in each corresponding app.
   - Never put complex query logic or cross-model mutations directly inside view functions or model methods.

6. **Queryset Security & Ownership Filtering**
   - **Every single queryset must be filtered by the logged-in user's role and ownership**:
     - `CLIENT`: Can ONLY view their own profile, requests, and issued confirmation documents.
     - `EMPLOYEE`: Can view assigned requests/tasks, associated clients, and upload documents for assigned requests.
     - `ADMIN`: Full visibility across all clients, employees, requests, and documents.
   - Never expose an unfiltered `.all()` in client- or employee-facing views.

7. **Application Structure**
   - `accounts`: Custom user model, authentication (login, logout, client signup), employee management for admin.
   - `catalog`: CA service catalog (tax filing, GST, audit, incorporation, etc.) with pricing and descriptions.
   - `requests`: Client service requests lifecycle (submission by client, status tracking, assignment to employee).
   - `documents`: Upload and secure retrieval of confirmation documents attached to requests.
   - `dashboards`: Role-tailored dashboards (`/dashboard/client/`, `/dashboard/employee/`, `/dashboard/admin/`).

8. **Configuration & Environments**
   - Settings split into `base.py`, `local.py`, and `prod.py`.
   - Environment variables managed via `django-environ` with a `.env` file (see `.env.example`).
   - SQLite for local development; PostgreSQL for production.

9. **Testing Policy**
   - Write tests as we go for every app and feature.
   - Every service function and view permission must have corresponding automated unit/integration tests (`tests.py` or `tests/`).

---

## Tech Stack
- **Backend**: Python 3.12+, Django 5.x
- **Database**: PostgreSQL (production), SQLite (local development)
- **Frontend**: Django Templates (MVT) + Bootstrap 5 + Bootstrap Icons
- **Config**: `django-environ`

---

## Common Commands

```bash
# Set settings module (if not using manage.py default)
export DJANGO_SETTINGS_MODULE=config.settings.local  # Linux/macOS
$env:DJANGO_SETTINGS_MODULE="config.settings.local"  # Windows PowerShell

# Migrations
python manage.py makemigrations
python manage.py migrate

# Create initial CA Admin
python manage.py createsuperuser

# Run local development server
python manage.py runserver

# Run tests
python manage.py test
```
