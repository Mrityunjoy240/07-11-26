#!/usr/bin/env bash
# =============================================================================
# DOGRAH WHITE-LABELING SETUP
# Fork Dograh and rebrand it as College Voice Agent
#
# Usage: bash dograh/fork-and-brand.sh
# Run this once after cloning the repo to set up your branded Dograh fork.
# =============================================================================
set -euo pipefail

COLLEGE_NAME="${COLLEGE_NAME:-Dr. B.C. Roy Engineering College}"
FORK_DIR="dograh-fork"
DOGRAH_UPSTREAM="https://github.com/dograh-hq/dograh.git"

echo "=== Step 1: Fork Dograh upstream ==="
echo "Go to https://github.com/dograh-hq/dograh and click Fork."
echo "Clone your fork:"
echo "  git clone https://github.com/YOUR_ORG/dograh.git $FORK_DIR"
echo ""
echo "Then run the remaining steps inside the fork."

read -p "Press Enter after you have forked and cloned Dograh... "

# -------------------------------------------------------------------------
# Step 2: Rebrand the UI
# -------------------------------------------------------------------------
echo "=== Step 2: Rebranding UI ==="

# Replace app name/title
find "$FORK_DIR/apps/ui" -type f \( -name "*.tsx" -o -name "*.ts" -o -name "*.json" \) -exec grep -l "Dograh" {} \; | while read f; do
    sed -i 's/Dograh/College Voice Agent/g' "$f"
    sed -i 's/dograh/college-voice-agent/g' "$f"
done

# Replace favicon and logos (replace with your college logo)
echo "Replace these files with your college branding:"
echo "  $FORK_DIR/apps/ui/public/favicon.ico"
echo "  $FORK_DIR/apps/ui/public/logo.svg"
echo "  $FORK_DIR/apps/ui/public/og-image.png"

# -------------------------------------------------------------------------
# Step 3: Rebrand the API
# -------------------------------------------------------------------------
echo "=== Step 3: Rebranding API ==="
sed -i 's/Dograh/College Voice Agent/g' "$FORK_DIR/apps/api/constants.py" 2>/dev/null || true
sed -i 's/dograh/college-voice-agent/g' "$FORK_DIR/apps/api/constants.py" 2>/dev/null || true

# Update the title/description in main.py
find "$FORK_DIR/apps/api" -name "main.py" -exec sed -i 's/title="Dograh"/title="College Voice Agent"/g' {} \; 2>/dev/null || true
find "$FORK_DIR/apps/api" -name "main.py" -exec sed -i 's/description=".*"/description="College admissions voice agent - Dr. B.C. Roy Engineering College"/g' {} \; 2>/dev/null || true

# -------------------------------------------------------------------------
# Step 4: Change theme colors
# -------------------------------------------------------------------------
echo "=== Step 4: Updating theme colors ==="
# Find and replace primary color in Tailwind config
if [ -f "$FORK_DIR/apps/ui/tailwind.config.ts" ]; then
    sed -i 's/#6366f1/#1a56db/g' "$FORK_DIR/apps/ui/tailwind.config.ts"
fi

# -------------------------------------------------------------------------
# Step 5: Build custom Docker images
# -------------------------------------------------------------------------
echo "=== Step 5: Build custom Docker images ==="
echo "From inside the fork directory, run:"
echo "  docker build -t your-registry/dograh-api:latest -f apps/api/Dockerfile ."
echo "  docker build -t your-registry/dograh-ui:latest -f apps/ui/Dockerfile ."
echo "  docker push your-registry/dograh-api:latest"
echo "  docker push your-registry/dograh-ui:latest"
echo ""
echo "Then update .env in the main project:"
echo "  DOGRAH_REGISTRY=your-registry"
echo "  DOGRAH_VERSION=latest"

# -------------------------------------------------------------------------
# Step 6: (Optional) Remove telemetry
# -------------------------------------------------------------------------
echo "=== Step 6: Remove telemetry (optional) ==="
grep -rl "posthog" "$FORK_DIR/apps/ui" --include="*.ts" --include="*.tsx" 2>/dev/null | while read f; do
    echo "Check telemetry in: $f"
done

echo ""
echo "=== White-labeling complete! ==="
echo "Your forked Dograh is now branded as College Voice Agent."
echo "Update DOGRAH_REGISTRY in your .env to point to your custom images."
