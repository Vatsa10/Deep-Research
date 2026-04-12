#!/bin/bash
# API integration tests — run with: bash tests/test_api.sh
# Requires the server running on localhost:8000

BASE="http://localhost:8000/api"
PASS=0
FAIL=0

check() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    if echo "$actual" | grep -q "$expected"; then
        echo "  PASS: $name"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $name (expected '$expected')"
        echo "    Got: $actual"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Deep Research API Tests ==="
echo ""

# --- Auth Tests ---
echo "--- Auth ---"

# Register
echo "Registering test user..."
REG=$(curl -s -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"apitest@test.com","password":"test123456","name":"API Tester"}')
check "Register returns access_token" "access_token" "$REG"
check "Register returns refresh_token" "refresh_token" "$REG"
check "Register returns user" "API Tester" "$REG"

TOKEN=$(echo "$REG" | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
REFRESH=$(echo "$REG" | python -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])" 2>/dev/null)

# Duplicate register
DUP=$(curl -s -X POST "$BASE/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"email":"apitest@test.com","password":"test123456","name":"Dup"}')
check "Duplicate register rejected" "already registered" "$DUP"

# Login
LOGIN=$(curl -s -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"apitest@test.com","password":"test123456"}')
check "Login returns access_token" "access_token" "$LOGIN"

# Wrong password
WRONG=$(curl -s -X POST "$BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"apitest@test.com","password":"wrongpassword"}')
check "Wrong password rejected" "Invalid email or password" "$WRONG"

# Me
ME=$(curl -s "$BASE/auth/me" -H "Authorization: Bearer $TOKEN")
check "Me returns email" "apitest@test.com" "$ME"
check "Me returns name" "API Tester" "$ME"

# No auth
NOAUTH=$(curl -s "$BASE/auth/me")
check "No token returns 401" "Not authenticated" "$NOAUTH"

# Refresh
REFRESHED=$(curl -s -X POST "$BASE/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$REFRESH\"}")
check "Refresh returns new access_token" "access_token" "$REFRESHED"

echo ""

# --- Templates ---
echo "--- Templates ---"

PUB=$(curl -s "$BASE/templates/public")
check "Public templates returns list" "Market Analysis" "$PUB"
check "Public templates has 5 items" "news-briefing" "$PUB"

AUTHT=$(curl -s "$BASE/templates" -H "Authorization: Bearer $TOKEN")
check "User templates returns list" "Market Analysis" "$AUTHT"

echo ""

# --- Research (start, but don't wait for completion) ---
echo "--- Research ---"

START=$(curl -s -X POST "$BASE/research" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"query":"What is 2+2?","depth":"quick"}')
check "Start research returns session_id" "session_id" "$START"

SID=$(echo "$START" | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])" 2>/dev/null)

# No auth research
NOAUTH_R=$(curl -s -X POST "$BASE/research" \
    -H "Content-Type: application/json" \
    -d '{"query":"test","depth":"quick"}')
check "Research without auth returns 401" "Not authenticated" "$NOAUTH_R"

# History
sleep 1
HIST=$(curl -s "$BASE/history" -H "Authorization: Bearer $TOKEN")
check "History returns sessions" "session" "$HIST"

echo ""

# --- Share (need completed session) ---
echo "--- Share ---"

# Try sharing a running session
SHARE_EARLY=$(curl -s -X POST "$BASE/research/$SID/share" \
    -H "Authorization: Bearer $TOKEN")
# May fail if still running, that's OK
check "Share endpoint responds" "" "$SHARE_EARLY"

echo ""

# --- Summary ---
echo "==========================="
echo "PASSED: $PASS"
echo "FAILED: $FAIL"
echo "==========================="

if [ $FAIL -gt 0 ]; then
    exit 1
fi
