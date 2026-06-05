# Travel Company API

REST API for managing travel projects and places, built with Django REST Framework.

---

## Requirements

- Docker & Docker Compose

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Paul-Starodub/Travel_company
cd travel_company
```

### 2. Create `.env` file

```env
SECRET_KEY=your-secret-key-here
DEBUG=False

POSTGRES_DB=travel_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=db
POSTGRES_PORT=5432

ART_INSTITUTE_API_URL=https://api.artic.edu/api/v1
```

### 3. Build and start all services

```bash
docker compose up --build
```

Migrations run automatically on startup. The API will be available at `http://localhost:8000`.

### 4. Create a superuser (optional)

```bash
docker compose exec web python manage.py createsuperuser
```

---

## API Documentation

Interactive docs are available after starting the server:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/api/doc/swagger/` | Swagger UI |
| `http://localhost:8000/api/doc/redoc/` | ReDoc |
| `http://localhost:8000/api/schema/` | OpenAPI schema (JSON) |

---

## Authentication

The API uses **JWT authentication** (via `djangorestframework-simplejwt`). All endpoints require a valid `Bearer` token except registration and login.

### Register

```http
POST /api/auth/users/
```

```json
{
  "username": "john",
  "password": "securepassword123",
  "email": "optional@gmail.com"
}
```

### Obtain tokens

```http
POST /api/auth/jwt/create/
```

```json
{
  "username": "john",
  "password": "securepassword123"
}
```

**Response:**

```json
{
  "access": "<access_token>",
  "refresh": "<refresh_token>"
}
```

Access token lifetime: **30 minutes**. Refresh token lifetime: **30 days**.

### Refresh access token

```http
POST /api/auth/jwt/refresh/
```

```json
{
  "refresh": "<refresh_token>"
}
```

### Using the token

Add the `Authorization` header to every request:

```
Authorization: Bearer <access_token>
```

### Get current user

```http
GET /api/auth/users/me/
```

---

## API Endpoints

### Travel Projects

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/projects/` | List all projects |
| `POST` | `/api/projects/` | Create a project |
| `GET` | `/api/projects/{id}/` | Get a single project |
| `PUT` | `/api/projects/{id}/` | Full update of a project |
| `PATCH` | `/api/projects/{id}/` | Partial update of a project |
| `DELETE` | `/api/projects/{id}/` | Delete a project |


#### Create a project with places

```http
POST /api/projects/
```

```json
{
  "name": "Italy Trip",
  "start_date": "2026-09-01",
  "places_input": [
    { "external_id": "27992", "notes": "Must see the main hall" },
    { "external_id": "11434" }
  ]
}
```

`description` and `start_date` are optional.

#### List projects — query parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `search` | string | Search by name or description |
| `ordering` | string | `name`, `start_date` (prefix `-` for descending) |
| `completed` | boolean | `true` / `false` — filter by completion status |
| `page` | integer | Page number |
| `page_size` | integer | Results per page (max 100, default 10) |

#### Update a project

```http
PATCH /api/projects/1/
```

```json
{
  "name": "Updated Name"
}
```

> A project **cannot be deleted** if any of its places are marked as `visited`. Returns `400` in that case.

---

### Places

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/projects/{id}/places/` | List all places in a project |
| `POST` | `/api/projects/{id}/places/` | Add one or more places to a project |
| `GET` | `/api/projects/{id}/places/{id}/` | Get a single place |
| `PUT` | `/api/projects/{id}/places/{id}/` | Full update of a place |
| `PATCH` | `/api/projects/{id}/places/{id}/` | Partial update of a place |

#### Add a single place

```http
POST /api/projects/1/places/
```

```json
{
  "external_id": "27992",
  "notes": "Second floor, room 3"
}
```

#### Add multiple places at once

```http
POST /api/projects/1/places/
```

```json
[
  { "external_id": "27992", "notes": "Main hall" },
  { "external_id": "11434" },
  { "external_id": "185651" }
]
```

Both single object and array are accepted. Response is always an array.

#### Update a place

```http
PATCH /api/projects/1/places/3/
```

```json
{
  "visited": true
}
```

```json
{
  "notes": "Visited on day 2, breathtaking"
}
```

---

## Business Rules & Validations

- A project can have **at most 10 places**
- Places are validated against the **Art Institute of Chicago API** before being stored — invalid `external_id` returns `400`
- The same place cannot be added to the same project more than once
- A project is considered **completed** when all its places are marked as `visited`
- A project **cannot be deleted** if it has any visited places

---

## Third-party API

Places are validated using the [Art Institute of Chicago API](https://api.artic.edu/docs/).

```
GET https://api.artic.edu/api/v1/artworks/{id}
```

Responses are cached for **1 hour** to reduce external API calls.