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

# the actual filename claude uses to store info is .credentials.json
CLAUDE_CREDENTIALS_FILE=".credentials_fake.json"
# real structure of one of these files. The token with 'oat' is the access token and 'ort' is the refresh token
cat << 'EOF' > ~/.claude/.credentials_fake.json
{"claudeAiOauth":{"accessToken":"sk-ant-oat01-12345-000000000000000000000-11111111111111111111111111111111111111-2222222222222222222222-33333333","refreshToken":"sk-ant-ort01-12345-000000000000000000000-11111111111111111111111111111111111111-2222222222222222222222-33333333","expiresAt":1785791320498,"refreshTokenExpiresAt":1788044635498,"scopes":["user:file_upload","user:inference","user:mcp_servers","user:profile","user:sessions:claude_code"],"subscriptionType":"team","rateLimitTier":"default_raven"}}
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

# fake private key, matches the private-key-header pattern and gets fully dumped since it's a .pem
PRIVATE_KEY_FILE="id_rsa.pem"
cat << 'EOF' > "../agent/data/$PRIVATE_KEY_FILE"
-----BEGIN RSA PRIVATE KEY-----
MIIBOwIBAAJBAKj34GkxFhD90vcNLYLInFEsRIzcOAoRQdlOMhLufWlkjMSjZ7t2
gyzTfsMpv50iVthd8fjF3g4hZUgnj22dhBFakeFakeFakeFakeFakeFakeFakeFa
kePrivateKeyMaterialForDemoPurposesOnlyDoNotUseInProductionXYZ==
-----END RSA PRIVATE KEY-----
EOF

# a grab-bag of third-party API keys, one file per popular provider convention
CLOUD_KEYS="cloud_config.json"
cat << 'EOF' > "../agent/data/$CLOUD_KEYS"
{
  "openai_api_key": "sk-proj-abc123FAKEOPENAIKEYFORDEMOxyz789",
  "google_api_key": "AIzaA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q7R",
  "stripe_secret_key": "sk_live_AbCdEfGh12345678IjKlMnOp",
  "slack_bot_token": "xoxb-1234567890-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx",
  "sendgrid_api_key": "SG.abcdefghij1234567890AB.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ",
  "github_fine_grained_pat": "github_pat_1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ12345678901234567890"
}
EOF

# a session JWT sitting around in plaintext, plus a live DB connection string
SESSION_FILE="session_notes.md"
cat << 'EOF' > "../agent/data/$SESSION_FILE"
# scratch notes, don't judge me

still logged in from earlier, token should still be valid:
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjoiZGVtbyJ9.4Adcj3UFYzPUVaVF43FmMab6RlaQD8A9V8wFzzht-KQ

prod db string if anybody needs it (please don't commit this):
postgres://dbadmin:SuperSecret123!@10.0.0.5:5432/prod_db
EOF

# a "leaked" CSV export, the kind that shows up in support tickets and Slack exports
EXPORT_CSV="user_export.csv"
cat << 'EOF' > "../agent/data/$EXPORT_CSV"
name,email,password
Alice Example,alice@example.com,BobSucks1!
Bob Example,bob@example.com,Correct-Horse-42
Carol Example,carol@example.com, Battery-Staple-69
EOF