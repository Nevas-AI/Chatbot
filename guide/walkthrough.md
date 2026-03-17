# Deploying Neva Chatbot on Hostinger VPS

> Complete guide: GitHub → Hostinger VPS with subdomain for dashboard

---

## Architecture Overview

```
yourdomain.com/api/*        → FastAPI backend (port 8000)
yourdomain.com/widget/*     → Static widget JS
dashboard.yourdomain.com    → React dashboard (built static files)
```

---

## Step 1: DNS Setup in Hostinger

In your Hostinger DNS Zone Editor, add these records:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `@` | `YOUR_VPS_IP` | 3600 |
| A | [dashboard](file:///c:/Users/Nevas/.gemini/antigravity/scratch/chatbot-project/backend/dashboard_routes.py#211-217) | `YOUR_VPS_IP` | 3600 |

> [!TIP]
> Replace `YOUR_VPS_IP` with your actual Hostinger VPS IP address. DNS propagation takes 5-30 minutes.

---

## Step 2: Push Project to GitHub

On your **local machine**, initialize and push the project:

```bash
cd chatbot-project
git init
git add .
git commit -m "Initial commit - Neva Chatbot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/chatbot-project.git
git push -u origin main
```

---

## Step 3: SSH into Your VPS

```bash
ssh root@YOUR_VPS_IP
```

---

## Step 4: Install System Dependencies

```bash
# Update system
apt update && apt upgrade -y

# Install essentials
apt install -y python3 python3-pip python3-venv nodejs npm nginx certbot python3-certbot-nginx git curl postgresql postgresql-contrib

# Verify versions
python3 --version   # Should be 3.10+
node --version      # Should be 18+
nginx -v
```

---

## Step 5: Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Pull the required models
ollama pull llama3.1
ollama pull nomic-embed-text

# Verify Ollama is running
systemctl status ollama
```

---

## Step 6: Setup PostgreSQL

```bash
# Switch to postgres user and create database
sudo -u postgres psql

# Inside psql:
CREATE USER neva_user WITH PASSWORD 'YOUR_SECURE_PASSWORD';
CREATE DATABASE neva_dashboard OWNER neva_user;
GRANT ALL PRIVILEGES ON DATABASE neva_dashboard TO neva_user;
\q
```

---

## Step 7: Clone Project from GitHub

```bash
cd /var/www
git clone https://github.com/YOUR_USERNAME/chatbot-project.git
cd chatbot-project
```

---

## Step 8: Setup Backend

```bash
cd /var/www/chatbot-project/backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install psycopg2-binary alembic

# Create production .env
cp .env .env.backup
```

Edit [.env](file:///c:/Users/Nevas/.gemini/antigravity/scratch/chatbot-project/backend/.env) with production values:

```bash
nano .env
```

```env
WEBSITE_URL=https://nevastech.com
COMPANY_NAME=Nevas Technologies
SUPPORT_EMAIL=info@nevastech.com
SUPPORT_PHONE=+91 0123456789
BUSINESS_HOURS=Mon-Sat 9AM-6PM IST

OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1
EMBEDDING_MODEL=nomic-embed-text

CHROMA_PERSIST_DIR=./chroma_db
CHROMA_COLLECTION_NAME=aria_knowledge

MAX_PAGES=100
AUTO_REFRESH_HOURS=24

# UPDATE THIS with your PostgreSQL credentials
DATABASE_URL=postgresql+asyncpg://neva_user:YOUR_SECURE_PASSWORD@localhost:5432/neva_dashboard

# Set a strong dashboard password
DASHBOARD_PASSWORD=YOUR_STRONG_DASHBOARD_PASSWORD
```

Run the database migration:

```bash
source venv/bin/activate
python -m alembic upgrade head
```

---

## Step 9: Create Systemd Service for Backend

```bash
nano /etc/systemd/system/neva-backend.service
```

Paste this:

```ini
[Unit]
Description=Neva Chatbot Backend
After=network.target postgresql.service ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/chatbot-project/backend
Environment=PATH=/var/www/chatbot-project/backend/venv/bin:/usr/bin
ExecStart=/var/www/chatbot-project/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable neva-backend
systemctl start neva-backend
systemctl status neva-backend
```

---

## Step 10: Build the Dashboard

```bash
cd /var/www/chatbot-project/dashboard

# Install dependencies
npm install

# Set the API URL for production build
export VITE_API_URL=https://yourdomain.com

# Build the static files
npx vite build
```

> [!IMPORTANT]
> If `tsc` fails, you can build with just Vite: `npx vite build`

The built files will be in `/var/www/chatbot-project/dashboard/dist/`

---

## Step 11: Configure Nginx

### Main domain (API + Widget)

```bash
nano /etc/nginx/sites-available/neva-api
```

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Widget static files
    location /widget/ {
        alias /var/www/chatbot-project/widget/;
        expires 1d;
        add_header Cache-Control "public, immutable";
        add_header Access-Control-Allow-Origin *;
    }

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support (for streaming chat)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # WebSocket support (for live chat)
    location /api/dashboard/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### Dashboard subdomain

```bash
nano /etc/nginx/sites-available/neva-dashboard
```

```nginx
server {
    listen 80;
    server_name dashboard.yourdomain.com;

    root /var/www/chatbot-project/dashboard/dist;
    index index.html;

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API calls from dashboard to backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # WebSocket
    location /api/dashboard/ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

Enable the sites:

```bash
ln -s /etc/nginx/sites-available/neva-api /etc/nginx/sites-enabled/
ln -s /etc/nginx/sites-available/neva-dashboard /etc/nginx/sites-enabled/

# Remove default site
rm -f /etc/nginx/sites-enabled/default

# Test and restart
nginx -t
systemctl restart nginx
```

---

## Step 12: Setup SSL (HTTPS) with Let's Encrypt

```bash
certbot --nginx -d yourdomain.com -d dashboard.yourdomain.com
```

Follow the prompts — Certbot will auto-configure HTTPS and redirect HTTP → HTTPS.

Auto-renewal is set up automatically. Test it:

```bash
certbot renew --dry-run
```

---

## Step 13: Update Dashboard API URL

After SSL, update the `VITE_API_URL` and rebuild:

```bash
cd /var/www/chatbot-project/dashboard
export VITE_API_URL=https://yourdomain.com
npx vite build
```

---

## Step 14: Update CORS in Backend

Edit [main.py](file:///c:/Users/Nevas/.gemini/antigravity/scratch/chatbot-project/backend/main.py) to restrict CORS to your actual domains:

```python
# In main.py, find the CORS middleware and update origins:
origins = [
    "https://yourdomain.com",
    "https://dashboard.yourdomain.com",
    "http://localhost:5173",  # keep for local dev
]
```

Restart backend:

```bash
systemctl restart neva-backend
```

---

## Step 15: Deploy Updates via GitHub

Whenever you push changes to GitHub, SSH into VPS and pull:

```bash
cd /var/www/chatbot-project
git pull origin main

# If backend changed:
cd backend
source venv/bin/activate
pip install -r requirements.txt
python -m alembic upgrade head
systemctl restart neva-backend

# If dashboard changed:
cd ../dashboard
npm install
VITE_API_URL=https://yourdomain.com npx vite build

# If widget changed: (no build needed, Nginx serves it directly)
```

### Optional: Auto-Deploy Script

Create `/var/www/chatbot-project/deploy.sh`:

```bash
#!/bin/bash
set -e

cd /var/www/chatbot-project
echo "📥 Pulling latest from GitHub..."
git pull origin main

echo "🐍 Updating backend..."
cd backend
source venv/bin/activate
pip install -r requirements.txt -q
python -m alembic upgrade head
systemctl restart neva-backend

echo "⚛️  Rebuilding dashboard..."
cd ../dashboard
npm install --silent
VITE_API_URL=https://yourdomain.com npx vite build

echo "✅ Deployment complete!"
```

```bash
chmod +x /var/www/chatbot-project/deploy.sh
```

Then deploy anytime with: `bash /var/www/chatbot-project/deploy.sh`

---

## Widget Embed Code

After deployment, embed the widget on any website:

```html
<script>
window.NevaConfig = {
  apiUrl: "https://yourdomain.com",
  clientId: "default"
};
</script>
<script src="https://yourdomain.com/widget/aria-widget.js"></script>
```

For different clients, change `clientId`:

```html
<script>
window.NevaConfig = {
  apiUrl: "https://yourdomain.com",
  clientId: "acme-corp"
};
</script>
<script src="https://yourdomain.com/widget/aria-widget.js"></script>
```

---

## Quick Reference

| Service | URL |
|---------|-----|
| API | `https://yourdomain.com/api/` |
| Dashboard | `https://dashboard.yourdomain.com` |
| Widget JS | `https://yourdomain.com/widget/aria-widget.js` |
| Widget Config | `https://yourdomain.com/api/widget/config/{slug}` |

| Command | Purpose |
|---------|---------|
| `systemctl status neva-backend` | Check backend status |
| `journalctl -u neva-backend -f` | View backend logs |
| `systemctl restart neva-backend` | Restart backend |
| `systemctl status nginx` | Check Nginx status |
| `bash /var/www/chatbot-project/deploy.sh` | Deploy updates |

---

> [!CAUTION]
> Remember to replace all placeholders: `yourdomain.com`, `YOUR_VPS_IP`, `YOUR_USERNAME`, `YOUR_SECURE_PASSWORD`, `YOUR_STRONG_DASHBOARD_PASSWORD`
