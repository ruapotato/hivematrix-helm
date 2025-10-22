#!/bin/bash
cd /home/david/Work/hivematrix/hivematrix-helm
source pyenv/bin/activate

# Get service token from Core
echo "Getting service token from Core..."
TOKEN=$(curl -s -X POST http://localhost:5000/service-token \
  -H "Content-Type: application/json" \
  -d '{"calling_service":"brainhair","target_service":"knowledgetree"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")

echo "Testing /api/browse endpoint..."
curl -s -H "Authorization: Bearer $TOKEN" \
     "http://127.0.0.1:5020/api/browse?path=/" | python3 -m json.tool
