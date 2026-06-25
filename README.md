# Apollo CRM

A self-hosted, lightweight CRM inspired by Apollo.io. Manage **companies** and **contacts**
in your own database, and use the **Apollo.io API only as a data source** to search and enrich
records. All selected and enriched data is stored in your own PostgreSQL database — there is no
dependency on Apollo for storage.

## Features

- **Dashboard** with company/contact totals, recently enriched companies, recent searches and Apollo API status.
- **Companies** list with search (name, domain, industry, country), enrichment-status filter, detail page with tabs (Overview, Contacts, Apollo data) and an *Enrich via Apollo* button.
- **Contacts** list with search (name, title, company, email), detail page, company linking and an *Enrich via Apollo* button.
- **Apollo Search** for both organizations and people with rich filters. Results are shown as a **preview** first; you save only the selected results into the CRM.
- **Settings** to manage the Apollo API key (stored **encrypted**), base URL, an enable/disable toggle and a connection test.
- **Auth** with JWT (login / register / me).
- Duplicate prevention: companies by domain, contacts by email or Apollo ID.
- **Alembic** migrations, **seed** data for development, full **Docker Compose** setup.

## Tech stack

| Layer     | Technology                          |
| --------- | ----------------------------------- |
| Backend   | FastAPI, SQLAlchemy 2, Pydantic v2  |
| Database  | PostgreSQL 16                       |
| Migrations| Alembic                             |
| Auth      | JWT (python-jose), passlib/bcrypt   |
| Frontend  | React + Vite, React Router          |
| Styling   | Tailwind CSS                        |
| Infra     | Docker + Docker Compose             |

## Quick start (Docker)

```bash
# 1. Copy environment defaults
cp .env.example .env        # On Windows PowerShell: copy .env.example .env

# 2. (Optional) edit .env — set a strong JWT_SECRET / ENCRYPTION_KEY for production.

# 3. Build and run everything
docker compose up --build
```

Then open:

- **Frontend**: http://localhost:8080
- **Backend API docs (Swagger)**: http://localhost:8000/docs

On first start the backend automatically:
1. runs Alembic migrations (`alembic upgrade head`),
2. seeds an admin user + Apollo settings row + demo data.

### Default login

```
email:    admin@apollo-crm.com
password: admin123
```

(Configurable via `ADMIN_EMAIL` / `ADMIN_PASSWORD` in `.env`.)

## Importing companies (Excel / CSV)

On the **Bedrijven** page, click **Importeren** to upload an `.xlsx` or `.csv` file.

- **Recognized columns**: `customer_name` (required), `country`, `domain`. Header names are
  case-insensitive and a few aliases are accepted (e.g. `company`, `name`, `land`, `website`).
- **All other columns** (e.g. `Product`, `Tier`, `Sector`, `mcp_id`, `revenue_2025`, …) are preserved
  in the company's `extra_data` and shown on the company detail page.
- **De-duplication / updates**: existing companies are matched by name or domain and **updated**
  (missing domain/country filled, `extra_data` merged) instead of being duplicated.
- **Enrich on import** (optional checkbox): after importing, each company that has a `domain` is
  enriched via Apollo to fill `industry`, `employee_count` and `revenue`. This **consumes Apollo
  credits** and requires the integration to be enabled in Settings. The `*_apollo` placeholder
  columns in your sheet are kept as-is in `extra_data`; the real values land in the dedicated fields.

## Configuring Apollo

1. Log in and go to **Instellingen** (Settings).
2. Paste your Apollo API key, set the base URL (default `https://api.apollo.io`) and toggle the integration **on**.
3. Click **Test verbinding** to verify the key.
4. Use **Apollo Search** to find organizations/people and save selected results, or use the
   *Verrijk via Apollo* button on any company/contact detail page.

The API key is encrypted at rest (Fernet) and is never logged in full.

## Apollo endpoints used

The service layer (`backend/app/services/apollo_service.py`) wraps the official Apollo API:

| Function                | Apollo endpoint                          |
| ----------------------- | ---------------------------------------- |
| `search_people`         | `POST /api/v1/mixed_people/search`       |
| `search_organizations`  | `POST /api/v1/mixed_companies/search`    |
| `enrich_person`         | `POST /api/v1/people/match`              |
| `enrich_people_bulk`    | `POST /api/v1/people/bulk_match`         |
| `enrich_organization`   | `POST /api/v1/organizations/enrich`      |

## API routes

```
Auth      POST /auth/login            POST /auth/register     GET  /auth/me
Companies GET/POST /companies         GET/PUT/DELETE /companies/{id}   POST /companies/{id}/enrich
Contacts  GET/POST /contacts          GET/PUT/DELETE /contacts/{id}    POST /contacts/{id}/enrich
Apollo    POST /apollo/search/people  POST /apollo/search/organizations
          POST /apollo/enrich/person  POST /apollo/enrich/people/bulk  POST /apollo/enrich/organization
          POST /apollo/save/people    POST /apollo/save/organizations  GET  /apollo/status
Settings  GET/PUT /settings/apollo    POST /settings/apollo/test
Dashboard GET /dashboard
```

## Local development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate      # Windows PowerShell:  .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Point to a running Postgres instance:
export DATABASE_URL="postgresql+psycopg://apollo:apollo@localhost:5432/apollo_crm"

alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
# Set the backend URL (defaults to http://localhost:8000)
echo "VITE_API_URL=http://localhost:8000" > .env
npm run dev
```

The dev server runs at http://localhost:5173.

## Database model

- **users** — id, name, email, password_hash, role, created_at
- **apollo_settings** — id, api_key_encrypted, base_url, enabled, created_at, updated_at
- **companies** — id, name, domain, website, linkedin_url, industry, employee_count, revenue, country, city, phone, description, apollo_id, source, enrichment_status, created_at, updated_at
- **contacts** — id, company_id, first_name, last_name, full_name, title, email, phone, linkedin_url, city, country, seniority, department, apollo_id, source, enrichment_status, created_at, updated_at
- **search_history** — id, query_type, query_payload, result_count, created_by, created_at
- **enrichment_logs** — id, entity_type, entity_id, endpoint, request_payload, response_status, created_at

## Project structure

```
.
├── docker-compose.yml
├── .env.example
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                # migrations
│   └── app/
│       ├── main.py
│       ├── seed.py
│       ├── core/               # config, database, security, crypto
│       ├── models/             # SQLAlchemy models
│       ├── schemas/            # Pydantic schemas
│       ├── services/           # Apollo service + mappers
│       └── api/routes/         # auth, companies, contacts, apollo, settings, dashboard
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    └── src/
        ├── api/                # axios client
        ├── context/            # auth + toast
        ├── components/         # layout + UI
        └── pages/              # Dashboard, Companies, Contacts, ApolloSearch, Settings, Login
```

## Security notes

- Set a strong, random `JWT_SECRET` and `ENCRYPTION_KEY` in production.
- Generate an encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Apollo API keys are encrypted with Fernet and masked everywhere they are displayed.
```
