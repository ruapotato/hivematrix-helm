#!/bin/bash
cd /home/david/Work/hivematrix/hivematrix-helm
source pyenv/bin/activate
TOKEN=$(python create_test_token.py 2>/dev/null)

echo "Testing brainhair AI - asking about ticket 17834..."
curl -s -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -X POST \
     -d '{"message":"Can you look up ticket 17834?"}' \
     http://127.0.0.1:5050/api/chat
