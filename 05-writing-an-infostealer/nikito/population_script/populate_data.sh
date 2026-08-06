#!/bin/bash

# This file is merely used to generate basic dummy data. The actual program scans for data in specific places, but in our demonstration
# we're using a box, so we need to put some crap here

mkdir ../agent/data

# Creating python code file, don't think too hard about the code

PYTHON_FILE="super_secure_file.py"

cat << 'EOF' > "../agent/data/$PYTHON_FILE"
from hell import aws

# Do not use in production you numpty - Claude
SUPER_SECRET_AWS_KEY = "AKIA0123456789ABCDEF"

def login_to_aws():
    aws.do_whatever_man_this_isnt_real(SUPER_SECRET_AWS_KEY)
EOF

# Making our .env file

ENV_FILE=".env"

cat << 'EOF' > "../agent/data/$ENV_FILE"
USER_EMAIL="bestvibecoderever@hotmail.com"
USER_PASS="Password123" # everybody stops trying after 12
GITHUB_PAT="ghp_tryingtofillthisto36charactersishard"
SOME_OTHER_SECRET="I've blindly accepted a PR several times"
EOF

# gonna add a fake claude conversation just for the hell of it
# this is the actual structure of how claude saves conversations
mkdir ~/.claude
mkdir ~/.claude/projects

CLAUDE_CONVO_DIR="~/.claude/projects/-home-nested-paths"
mkdir ~/.claude/projects/-home-nested-paths

CLAUDE_CONVO_FILE="$CLAUDE_CONVO_DIR/00001111-2222-3333-4444-5555-666677778888.jsonl"

cat << 'EOF' > ~/.claude/projects/-home-nested-paths/00001111-2222-3333-4444-5555-666677778888.jsonl
{"type":"queue-operation","operation":"enqueue","timestamp":"2026-07-22T13:49:22.632Z","sessionId":"0123-4567-89ab-cdef-fedcba9876543210"}
{"type":"queue-operation","operation":"dequeue","timestamp":"2026-07-22T13:49:22.633Z","sessionId":"0123-4567-89ab-cdef-fedcba9876543210"}
{"parentUUID":null,"isSidechain":false,"type":"user","message":{"role":"user", "content":[{"type":"text","text":"generate some badass program idec. make no mistakes either"}]}
{"parentUUID":null,"isSidechain":false,"type":"robit","message":{"role":"robit","content":[{"type:"text","text":"yo waddup, it's ya boy claude. Well actually it's a human typing some crap in the airport. I seriously doubt anybody is gonna ever read this. Anyways heres your discord token:Nabcdefghijklmnopqrstuvw.ABCDEF.abcdefghijklmnopqrstuvwxyz1 isn't that wacky?"}]}}
EOF


# conspicuous file
PASSWORD_FILE="password_list.txt"

cat << 'EOF' > "../agent/data/$PASSWORD_FILE"
facebook: hunter12
reddit: hunter12
work: Hunter12!
EOF

# list of IPs and emails
EMAILS="emails.txt"
cat << 'EOF' > "../agent/data/$EMAILS"
personal: bestvibecoderever@hotmail.com
work: melon.husk@funnyname.gov
EOF

IPS="ips.txt"
cat << 'EOF' > "../agent/data/$IPS"
127.0.0.1
172.168.1.2
8.8.8.8
123.45.67.89
EOF