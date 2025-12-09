#!/bin/bash

# Azure KYC Agent Orchestration - User Input Test Script
# This script tests the complete workflow with realistic user inputs

BASE_URL="http://localhost:8000"
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Azure KYC Agent Test - User Inputs${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Test Case 1: Complete Happy Path
echo -e "${GREEN}Test 1: Complete Happy Path${NC}"
echo -e "${YELLOW}Step 1.1: Create Session${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/start-session" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "email": "john.smith@example.com",
    "insurance_needs": "life insurance",
    "user_type": "employee"
  }')

SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
echo "Created session: $SESSION_ID"
echo ""

echo -e "${YELLOW}Step 1.2: Provide DOB and Address${NC}"
echo "User input: 'Customer DOB is 01.01.1980 and address is 123 Main St, New York, NY 10001'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Customer DOB is 01.01.1980 and address is 123 Main St, New York, NY 10001"
  }' | python3 -m json.tool | head -30
echo -e "\n"

echo -e "${YELLOW}Step 1.3: Provide Consent${NC}"
echo "User input: 'Customer provided consent for data collection and processing'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Customer provided consent for data collection and processing"
  }' | python3 -m json.tool | head -30
echo -e "\n"

echo -e "${YELLOW}Step 1.4: Provide Documents${NC}"
echo "User input: 'Customer submitted drivers license DL123456 and passport P987654321'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Customer submitted drivers license DL123456 and passport P987654321"
  }' | python3 -m json.tool | head -30
echo -e "\n"

# Test Case 2: Incremental Data Provision
echo -e "${GREEN}Test 2: Incremental Data Entry${NC}"
echo -e "${YELLOW}Step 2.1: Create Session${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/start-session" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "email": "jane.doe@example.com",
    "insurance_needs": "health insurance",
    "user_type": "employee"
  }')

SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
echo "Created session: $SESSION_ID"
echo ""

echo -e "${YELLOW}Step 2.2: Provide only DOB${NC}"
echo "User input: 'Date of birth: 15.06.1992'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Date of birth: 15.06.1992"
  }' | python3 -m json.tool | grep -A 5 -B 5 '"response"'
echo -e "\n"

echo -e "${YELLOW}Step 2.3: Provide Address${NC}"
echo "User input: 'Address is 456 Oak Avenue, Boston, MA 02101'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Address is 456 Oak Avenue, Boston, MA 02101"
  }' | python3 -m json.tool | grep -A 5 -B 5 '"response"'
echo -e "\n"

echo -e "${YELLOW}Step 2.4: Confirm Consent${NC}"
echo "User input: 'Yes, customer consents to data processing'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Yes, customer consents to data processing"
  }' | python3 -m json.tool | grep -A 5 -B 5 '"response"'
echo -e "\n"

# Test Case 3: Different Date Formats
echo -e "${GREEN}Test 3: Various Date Formats${NC}"
echo -e "${YELLOW}Step 3.1: ISO Format (yyyy-mm-dd)${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/start-session" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User ISO",
    "email": "iso@test.com",
    "insurance_needs": "auto insurance",
    "user_type": "employee"
  }')

SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
echo "User input: 'Customer was born on 1990-12-25'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Customer was born on 1990-12-25"
  }' | python3 -m json.tool | grep -A 3 '"date_of_birth"'
echo -e "\n"

echo -e "${YELLOW}Step 3.2: Slash Format (dd/mm/yyyy)${NC}"
SESSION_RESPONSE=$(curl -s -X POST "$BASE_URL/start-session" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User Slash",
    "email": "slash@test.com",
    "insurance_needs": "life insurance",
    "user_type": "employee"
  }')

SESSION_ID=$(echo $SESSION_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
echo "User input: 'DOB: 25/12/1990'"
curl -s -X POST "$BASE_URL/chat/$SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "DOB: 25/12/1990"
  }' | python3 -m json.tool | grep -A 3 '"date_of_birth"'
echo -e "\n"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo "Test 1: Complete happy path with all data provided"
echo "Test 2: Incremental data entry, one field at a time"
echo "Test 3: Various date format handling"
echo ""
echo "Review the responses above to verify:"
echo "  ✓ Data extraction working (DOB, address, consent)"
echo "  ✓ Agent recognizes provided data"
echo "  ✓ Auto-advancement on PASS decisions"
echo "  ✓ User-friendly REVIEW/FAIL messages"
