## DX Index Explorer API for OpenAI custom GPT🚀

Web server to explore and query industry/company data through a simple Flask API, protected with a Bearer API key. Health checks are public; everything else is secured.

### ✨ Features

- **Secure by default**: All endpoints require `Authorization: Bearer <API_KEY>` (except health `GET /`).
- **Environment-aware**: Dev server via `python main.py`; production via Gunicorn/`Procfile`.
- **.env support**: Configuration via environment variables using `python-dotenv`.

---

### ⚡ Quickstart

1) Create and activate a virtual environment, then install deps

```bash
python -m venv .venv && . .venv/Scripts/activate  # Windows PowerShell: . .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2) Create a `.env` with your API key

```env
API_KEY=replace-with-a-strong-secret
# Optional: set runtime mode. Anything other than PROD is treated as development
ENV=DEV
```

3) Run the API locally (development)

```bash
python main.py
```

4) Test it

```bash
# Health (no auth required)
curl http://localhost:5000/

# Authenticated request (replace TOKEN)
curl -H "Authorization: Bearer TOKEN" http://localhost:5000/industries
```

---

### 🔐 Authentication

- Send `Authorization: Bearer <API_KEY>` for all endpoints except health `GET /`.
- The API key is read from the `API_KEY` environment variable (via `.env` in development).

Generate a secure key (PowerShell):

```powershell
$b = New-Object 'Byte[]' 32; [System.Security.Cryptography.RandomNumberGenerator]::Fill($b); [System.Convert]::ToHexString($b)
```

Or with Python:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Append to `.env` (PowerShell):

```powershell
$KEY = (python -c "import secrets; print(secrets.token_urlsafe(32))"); Add-Content -Path .env -Value "API_KEY=$KEY"
```

---

### 🧰 Configuration

- **`API_KEY`**: Required. Bearer token used by clients.
- **`ENV`**: Optional. When set to `PROD`, local `python main.py` dev server will not run; use Gunicorn instead. Any other value (or unset) is treated as development.

---

### 🏗️ Run in Production

This project includes a `Procfile` and Gunicorn config.

- `Procfile`:

```txt
web: gunicorn --worker-tmp-dir /dev/shm --config gunicorn_config.py main:app
```

- `gunicorn_config.py` (defaults):

```python
bind = "0.0.0.0:8080"
workers = 2
```

Start with Gunicorn (example):

```bash
ENV=PROD API_KEY=replace-with-a-strong-secret \
  gunicorn --worker-tmp-dir /dev/shm --config gunicorn_config.py main:app
```

On platforms that read `Procfile` (e.g., PaaS), set `ENV=PROD` and `API_KEY` in the environment.

---

### 🧭 API Reference

Base URL (dev): `http://localhost:5000`

Authentication: `Authorization: Bearer <API_KEY>` required on all routes except `GET /`.

| Method | Path                                   | Description                    | Query/Body                                                      |
| -----: | -------------------------------------- | ------------------------------ | --------------------------------------------------------------- |
|    GET | `/`                                  | Health check (no auth)         | —                                                              |
|    GET | `/industries`                        | List industries                | —                                                              |
|    GET | `/industry/<industry>/companies`     | Companies in an industry       | `year`, `month`                                             |
|    GET | `/company`                           | Single company data            | `name` (required), `year`, `month`                        |
|   POST | `/companies`                         | Batch company data             | JSON body:`{ companies: [string], industry?, year?, month? }` |
|    GET | `/industry/<industry>/rank/<rank>`   | Nth-ranked company in industry | `year`, `month`                                             |
|    GET | `/industry/<industry>/rankings`      | Ranked list for industry       | `limit`, `offset`, `year`, `month`                      |
|    GET | `/industry/<industry>/overview`      | Industry overview              | —                                                              |
|    GET | `/industry/<industry>/top-companies` | Top companies in industry      | —                                                              |
|    GET | `/search/companies`                  | Search companies               | `q` (required), `limit`, `year`, `month`                |
|    GET | `/periods`                           | Available periods              | `industry`                                                    |

Example requests:

```bash
# Company by name
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:5000/company?name=Acme&year=2024&month=5"

# Batch companies
curl -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" \
  -d '{"companies":["Acme","Globex"],"industry":"tech","year":"2024","month":5}' \
  http://localhost:5000/companies
```

---

### 🗂️ Project Structure

```txt
app/
  __init__.py
  routes.py
  actions/actions.yaml
  services/service_industries.py
gunicorn_config.py
main.py
Procfile
requirements.txt
```

---

### 🧪 Health Check

```bash
curl http://localhost:5000/
```

Returns `Healthy.` with HTTP 200.

---

### 🧯 Troubleshooting

- **401/403 responses**: Ensure `Authorization: Bearer <API_KEY>` is present and correct.
- **`dotenv` import warning**: Confirm `python-dotenv` is installed in your current virtualenv.
- **Dev server didn’t start**: Check that `ENV` is not set to `PROD`.
- **Port conflicts**: Dev runs on `5000`; Gunicorn binds to `8080` in PROD env ()by default ).

---

### 🤝 Contributing

- Use descriptive commit messages and PRs.
- Keep code readable and consistent with the existing style.
