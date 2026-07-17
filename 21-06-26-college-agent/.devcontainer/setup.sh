#!/bin/bash
set -e

echo "=== College Voice Agent - Codespace Setup ==="
echo ""

# --- Backend .env ---
if [ ! -f backend/.env ]; then
    cp .env.example backend/.env

    # Use Codespace secrets if available
    if [ -n "$GROQ_API_KEY" ]; then
        sed -i "s/GROQ_API_KEY=.*/GROQ_API_KEY=$GROQ_API_KEY/" backend/.env
    fi
    if [ -n "$SARVAM_API_KEY" ]; then
        sed -i "s/SARVAM_API_KEY=.*/SARVAM_API_KEY=$SARVAM_API_KEY/" backend/.env
    fi

    echo "Created backend/.env"
    echo ">>> Add API keys if missing: groq, sarvam <<<"
fi

# --- Root .env (Dograh config) ---
if [ ! -f .env ]; then
    cp .env.example .env
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null || echo "change-me")
    sed -i "s/OSS_JWT_SECRET=/OSS_JWT_SECRET=$JWT_SECRET/" .env
    echo "Created root .env with generated OSS_JWT_SECRET"
fi

# Install Python deps
echo ""
echo "Installing Python dependencies..."
cd backend
pip install -r requirements.txt -q
cd ..

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Quick test (no Docker):"
echo "  cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "Full stack (with telephony):"
echo "  docker compose up -d"
echo "  (opens http://localhost:3010 for Dograh UI)"
