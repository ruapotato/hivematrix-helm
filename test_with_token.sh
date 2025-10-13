#!/bin/bash
cd /home/david/Work/hivematrix/hivematrix-helm
source pyenv/bin/activate
TOKEN=$(python create_test_token.py 2>/dev/null)

echo "Testing KnowledgeTree /browse with auth token..."
echo ""
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:5020/knowledgetree/browse/
