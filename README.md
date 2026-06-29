# Django News Application

A news platform with role-based access control, article approval workflows, newsletter management, subscriber email notifications, and a REST API built with Django REST Framework.

## Roles

| Role | Permissions |
|------|-------------|
| **Reader** | Browse & read approved articles and newsletters; subscribe to journalists/publishers |
| **Journalist** | Create, edit, delete own articles and newsletters |
| **Editor** | Full access — approve articles, manage all content |

---

## Running with a virtual environment

### Prerequisites
- Python 3.10+
- pip / pip3

### Setup

```bash
# 1. Clone the repo
git clone <your-repo-url>
cd django-news-application

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file (see below)
cp .env.example .env            # if provided, otherwise create manually

# 5. Run migrations
python manage.py migrate

# 6. Create role groups
python manage.py setup_groups

# 7. Create a superuser (optional)
python manage.py createsuperuser

# 8. Start the development server
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`.

---

## Environment variables

Create a `.env` file in the project root with the following variables. **Never commit this file** — it is excluded by `.gitignore`.

```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Email backend (use console backend for local development)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=noreply@example.com

# X (Twitter) API credentials — optional; leave blank to skip posting
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_TOKEN_SECRET=
X_BEARER_TOKEN=
```

Generate a secret key with:
```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

---

## Running with Docker

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running

### Build and run

```bash
# 1. Build the image
docker build -t django-news-app .

# 2. Run the container (pass env vars inline or via --env-file)
docker run -d \
  --name news-app \
  -p 8000:8000 \
  --env-file .env \
  django-news-app

# 3. Run migrations inside the container
docker exec news-app python manage.py migrate
docker exec news-app python manage.py setup_groups

# 4. (Optional) Create a superuser
docker exec -it news-app python manage.py createsuperuser
```

The application will be available at `http://localhost:8000/`.

### Stop and remove the container

```bash
docker stop news-app && docker rm news-app
```

---

## Documentation

Sphinx-generated HTML documentation is available in [`docs/build/html/`](docs/build/html/index.html).

To rebuild the docs:

```bash
pip install sphinx
python -m sphinx.cmd.build docs/source docs/build/html
```

---

## REST API overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/register/` | Register a new user |
| POST | `/api/token/` | Obtain JWT token pair |
| POST | `/api/token/refresh/` | Refresh access token |
| GET/POST | `/api/articles/` | List approved articles / create article |
| GET | `/api/articles/subscribed/` | Articles from subscribed sources |
| GET/PUT/DELETE | `/api/articles/<id>/` | Retrieve / update / delete article |
| POST | `/api/articles/<id>/approve/` | Approve article (Editor only) |
| GET/POST | `/api/newsletters/` | List / create newsletters |
| GET/PUT/DELETE | `/api/newsletters/<id>/` | Retrieve / update / delete newsletter |
| GET | `/api/publishers/` | List publishers |
| GET/PUT | `/api/profile/` | View or update own profile |
