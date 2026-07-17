#!/usr/bin/env bash
# =============================================================================
# COLLEGE AGENT SETUP
# Creates a Dograh voice agent that uses our RAG API for answers.
#
# Prerequisites:
#   1. Dograh must be running (docker compose up -d dograh-api ...)
#   2. Our backend must be running (docker compose up -d backend)
#   3. JWT token from Dograh admin login
#
# Usage:
#   DOGRAH_JWT=<token> bash dograh/setup-agent.sh
#
# Or run interactively:
#   1. Login to Dograh UI at http://localhost:3010
#   2. Create admin account (first-run setup)
#   3. Get JWT from browser dev tools → Application → Local Storage → jwt_token
#   4. Run this script
# =============================================================================
set -euo pipefail

DOGRAH_API="${DOGRAH_API:-http://localhost:8001}"
BACKEND_API="${BACKEND_API:-http://backend:8080}"
JWT="${DOGRAH_JWT:-}"

if [ -z "$JWT" ]; then
    echo "ERROR: Set DOGRAH_JWT=<your_token>"
    echo "Login to Dograh UI at http://localhost:3010, then get JWT from browser dev tools."
    exit 1
fi

AUTH_HEADER="Authorization: Bearer $JWT"
CONTENT_TYPE="Content-Type: application/json"

echo "=== Creating college knowledge tool (HTTP API) ==="

# Create an HTTP API Tool that Dograh's agent will call to get answers
TOOL_RESPONSE=$(curl -s -X POST "$DOGRAH_API/api/v1/tools" \
  -H "$AUTH_HEADER" \
  -H "$CONTENT_TYPE" \
  -d '{
    "name": "query_college_knowledge_base",
    "description": "Query the college knowledge base for admissions info, fees, courses, faculty, placements. Use this when the caller asks about anything related to the college.",
    "type": "http_api",
    "config": {
      "method": "POST",
      "url": "'"$BACKEND_API"'/qa/query",
      "headers": {
        "Content-Type": "application/json"
      },
      "body": {
        "message": "{{input}}"
      },
      "response_mapping": {
        "result_path": "$.answer"
      }
    },
    "parameters": [
      {
        "name": "input",
        "type": "string",
        "description": "The caller'\''s question about the college, exactly as spoken",
        "required": true
      }
    ]
  }')

echo "Tool response: $TOOL_RESPONSE"
TOOL_ID=$(echo "$TOOL_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

echo ""
echo "=== Creating voice agent ==="

# Create the voice agent workflow
AGENT_RESPONSE=$(curl -s -X POST "$DOGRAH_API/api/v1/agents" \
  -H "$AUTH_HEADER" \
  -H "$CONTENT_TYPE" \
  -d '{
    "name": "College Admissions Agent",
    "description": "Multilingual voice agent for college admissions inquiries. Handles English, Hindi, and Bengali.",
    "workflow_definition": {
      "nodes": [
        {
          "id": "start",
          "type": "start_call",
          "config": {
            "prompt": "Namaste! Welcome to Dr. B.C. Roy Engineering College. I am your admissions assistant. I can answer your questions about courses, fees, placements, and more. How can I help you today? नमस्ते! डॉ. बी.सी. रॉय इंजीनियरिंग कॉलेज में आपका स्वागत है। मैं आपकी प्रवेश सहायक हूं। मैं कोर्स, फीस, प्लेसमेंट और अधिक के बारे में आपके सवालों का जवाब दे सकता हूं। मैं आपकी कैसे मदद कर सकता हूं?",
            "allow_interruption": false
          }
        },
        {
          "id": "agent",
          "type": "agent",
          "config": {
            "prompt": "You are a friendly college admissions assistant for Dr. B.C. Roy Engineering College. Answer callers'\'' questions clearly and concisely.\n\nWhen you need information about courses, fees, placements, or admissions:\n1. Use the query_college_knowledge_base tool to get accurate information\n2. Always respond in the same language the caller used (Hindi/English/Bengali)\n3. If you don'\''t know something, use the tool to look it up\n4. Keep answers brief and natural for a phone conversation\n5. After answering, ask if there'\''s anything else you can help with",
            "model": "gpt-4o-mini",
            "tools": ["'"$TOOL_ID"'"],
            "allow_interruption": true,
            "max_duration_seconds": 600
          }
        },
        {
          "id": "end",
          "type": "end_call",
          "config": {
            "prompt": "Thank you for calling Dr. B.C. Roy Engineering College! If you have more questions, feel free to call again. Have a great day! धन्यवाद! फिर कभी कॉल करने पर संकोच न करें। आपका दिन शुभ हो!"
          }
        }
      ],
      "edges": [
        {"source": "start", "target": "agent"},
        {"source": "agent", "target": "end", "condition": "caller_says_goodbye"}
      ]
    }
  }')

echo "Agent response: $AGENT_RESPONSE"
AGENT_ID=$(echo "$AGENT_RESPONSE" | python -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

echo ""
echo "=== Agent created! ==="
echo "Agent ID: $AGENT_ID"
echo ""
echo "Next steps:"
echo "1. Go to Dograh UI at http://localhost:3010"
echo "2. Navigate to the agent workflow to review/edit"
echo "3. Configure telephony (Twilio/Vonage) in Settings"
echo "4. Bind a phone number to this agent"
echo "5. Test with a web call first"
echo ""
echo "To test without telephony, use Dograh's test run API:"
echo "  curl -X POST \"$DOGRAH_API/api/v1/agents/$AGENT_ID/runs\" \\"
echo "    -H \"$AUTH_HEADER\" \\"
echo "    -H \"$CONTENT_TYPE\" \\"
echo '    -d "{\"input\": \"What courses do you offer?\"}"'
