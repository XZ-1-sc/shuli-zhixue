# Docker Layout

Docker-related files are kept under this directory so the project root stays clean.

```text
docker/
  backend/
    Dockerfile
  nginx/
    default.conf
```

The root `docker-compose.yml` is the only Docker file left at the project entry because Docker Compose expects it there by default.

Use the unified local entry:

```text
http://localhost:8080
```
