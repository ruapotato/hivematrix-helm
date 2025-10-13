#!/bin/bash
# Start KnowledgeTree and capture error when we hit it
cd /home/david/Work/hivematrix/hivematrix-knowledgetree
source pyenv/bin/activate

# Start in background, logging to file
python run.py > /tmp/kt_output.log 2>&1 &
KT_PID=$!

echo "Started KnowledgeTree (PID $KT_PID), waiting for startup..."
sleep 3

# Test the endpoint
echo "Testing endpoint..."
cd /home/david/Work/hivematrix/hivematrix-helm
./test_with_token.sh

# Give it a moment for the error to be logged
sleep 2

# Show the logs
echo ""
echo "==================== KnowledgeTree Output ===================="
tail -50 /tmp/kt_output.log

# Kill the process
kill $KT_PID 2>/dev/null
