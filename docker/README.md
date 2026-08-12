# Docker Layout

Docker-related files are kept under this directory so the project root stays clean.

```text
docker/
  backend/
    Dockerfile
  gateway/
    Dockerfile
  nginx/
    default.conf
```

The root `docker-compose.yml` is the only Docker file left at the project entry because Docker Compose expects it there by default.

`gateway` is a multi-stage image: it builds the Vue frontend with Node and then serves `frontend/dist` with Nginx. Nginx keeps proxying `/api/*`, `/docs`, and `/openapi.json` to the FastAPI backend.

Student answer images are stored in the named volume `math_answer_uploads`, so rebuilding or recreating the backend container does not delete submitted images.

Use the unified local entry:

```text
http://localhost:8080
```
