# Deploy on AWS EC2 with Docker (config from `.env`, no SSM)

Assumes an Ubuntu 22.04/24.04 EC2 instance you can SSH into, with a GitHub deploy key already installed for
`git@github.com:zinazimystic/rc2-ats.git`. The database stays on Supabase (IPv4 session pooler works from EC2).

## 0. Instance and network
- Size: **t3.medium** (4 GB) or larger. The Next.js image build needs memory; on a t3.small add swap (step 1).
- Security group inbound: **22** from your IP only, **80** from anywhere (**443** too if you add HTTPS). Do NOT open 3000/8000.

## 1. Install Docker (once)
```bash
ssh ubuntu@<EC2_PUBLIC_IP>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
docker compose version            # must print v2.x

# only if the box has <= 2 GB RAM:
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
```

## 2. Get the code
```bash
git clone git@github.com:zinazimystic/rc2-ats.git
cd rc2-ats
```

## 3. Create `backend/.env` on the server (not in git)
Either copy it from your laptop:
```bash
scp backend/.env ubuntu@<EC2_PUBLIC_IP>:~/rc2-ats/backend/.env
```
or create it with `nano backend/.env` using `backend/.env.example` as the template. Required values:
`DATABASE_URL` (Supabase session pooler, `postgresql+psycopg://...?sslmode=require`), `JWT_SECRET` (new long random value:
`openssl rand -hex 32`), `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL=deepseek-flash`, `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION=us-east-1`,
`BEDROCK_EMBED_MODEL`, `EMBEDDING_DIM=1024`, optional `RECRUITER_INVITE_CODE`. Lock it down: `chmod 600 backend/.env`.

**Bedrock key:** a *short-term* key expires after at most 12 hours. For a server create a **long-term Bedrock API key**
(Bedrock console -> API keys) and use that as `AWS_BEARER_TOKEN_BEDROCK`.

## 4. Build and start
```bash
docker compose -f docker-compose.ec2.yml up -d --build
docker compose -f docker-compose.ec2.yml ps
curl -s localhost/api/health                      # {"status":"ok", ...}
```
Open `http://<EC2_PUBLIC_IP>` in a browser. Tables are created automatically on first start.

## 5. Optional demo data
```bash
docker compose -f docker-compose.ec2.yml exec api python scripts/seed_demo.py --base-url http://localhost:8000/api
```
Sign in as `recruiter@demo.rc3.dev` / `Demo1234!`.

## Operate
```bash
docker compose -f docker-compose.ec2.yml logs -f api        # backend logs
git pull && docker compose -f docker-compose.ec2.yml up -d --build   # deploy an update
docker compose -f docker-compose.ec2.yml restart api        # after editing backend/.env
```
The backend runs ONE uvicorn worker on purpose (in-process task runner and rate limiter).

## Optional: HTTPS with a domain
Point an A record at the instance, publish web on loopback (`127.0.0.1:3000:3000` instead of `80:3000`), install Caddy
(`sudo apt install caddy`) with `/etc/caddy/Caddyfile`:
```
yourdomain.com {
    reverse_proxy 127.0.0.1:3000
}
```
then set `COOKIE_SECURE: "true"` in `docker-compose.ec2.yml` and rebuild.
