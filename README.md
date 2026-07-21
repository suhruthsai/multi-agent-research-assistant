multi-agent-research-assistant

## Docker

Build the image:

```bash
docker build -t mara-research-assistant .
```

Run it:

```bash
cp .env.docker.example .env.docker
# edit .env.docker and add GROQ_API_KEY
docker run --env-file .env.docker -p 3000:3000 -p 8000:8000 mara-research-assistant
```

Open:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health

If you set `MARA_API_KEY`, also build the frontend with the matching public key:

```bash
docker build \
  --build-arg NEXT_PUBLIC_MARA_API_KEY=your-local-key \
  -t mara-research-assistant .
```
