# API guide

Base URL path: `/api/v1`. All bodies are JSON. The machine-readable
contract is [openapi.json](openapi.json), regenerated with `make openapi`.

## Conventions

- Authentication: `Authorization: Bearer <token>` from `POST /sessions`
  (anonymous users) or `POST /auth/login` (seeded staff).
- Language: `?lang=en|ar` wins, else the `Accept-Language` prefix, else
  English. Unknown values fall back to English.
- Errors share one body: `{"error": {"code": "...", "message": "...",
  "details": {...}}}` with codes such as `CONSENT_REQUIRED`, `FORBIDDEN`,
  `NOT_FOUND`, `VALIDATION_ERROR`, `INVALID_TRANSITION`, `SHARE_EXPIRED`,
  `RATE_LIMITED` and `CONFLICT`.

## Demo journey (curl)

Point at a running API with a migrated database (see
[deployment](deployment.md)):

```sh
BASE=http://localhost:8000/api/v1

# 1. Anonymous session.
TOKEN=$(curl -s -X POST $BASE/sessions -H 'Content-Type: application/json' \
  -d '{}' | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
AUTH="Authorization: Bearer $TOKEN"

# 2. Grant intake consent (required before storing answers).
curl -s -X POST $BASE/consent -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"scope": "intake", "granted": true}'

# 3. Save intake answers (partial saves allowed).
curl -s -X PUT $BASE/intake -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"answers": {"diabetes": {"value": true, "status": "answered"}}}'

# 4. Run the assessment.
ASSESSMENT=$(curl -s -X POST "$BASE/assess?lang=en" -H "$AUTH")
echo "$ASSESSMENT" | python3 -m json.tool | head -20
AID=$(echo "$ASSESSMENT" | python3 -c 'import sys, json; print(json.load(sys.stdin)["assessment_id"])')

# 5. Regenerate the explanation and inspect the trace.
curl -s -X POST $BASE/explain -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"assessment_id\": \"$AID\"}"
curl -s $BASE/trace/$AID -H "$AUTH"

# 6. Browse providers and create a referral (non-self-care routes only).
curl -s "$BASE/providers?type=teleconsult" -H "$AUTH"
REF=$(curl -s -X POST $BASE/referrals -H "$AUTH" -H 'Content-Type: application/json' \
  -d "{\"assessment_id\": \"$AID\", \"type\": \"teleconsult\"}")
RID=$(echo "$REF" | python3 -c 'import sys, json; print(json.load(sys.stdin)["id"])')

# 7. Clinician review (seeded demo accounts; passwords live in .env).
CTOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"handle": "clinician-demo", "password": "clinician-demo"}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
CAUTH="Authorization: Bearer $CTOKEN"
curl -s $BASE/clinician/queue -H "$CAUTH"
curl -s -X POST $BASE/clinician/review -H "$CAUTH" -H 'Content-Type: application/json' \
  -d "{\"assessment_id\": \"$AID\", \"decision\": \"approved\"}"

# 8. Book, attend, explain and close with an outcome note.
curl -s -X PATCH $BASE/referrals/$RID/status -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"to_status": "booked", "appointment_time": "2027-01-15T10:00:00+00:00"}'
NTOKEN=$(curl -s -X POST $BASE/auth/login -H 'Content-Type: application/json' \
  -d '{"handle": "navigator-demo", "password": "navigator-demo"}' \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
NAUTH="Authorization: Bearer $NTOKEN"
curl -s -X PATCH $BASE/referrals/$RID/status -H "$NAUTH" -H 'Content-Type: application/json' \
  -d '{"to_status": "attended"}'
curl -s -X PATCH $BASE/referrals/$RID/status -H "$CAUTH" -H 'Content-Type: application/json' \
  -d '{"to_status": "result_explained"}'
curl -s -X PATCH $BASE/referrals/$RID/status -H "$CAUTH" -H 'Content-Type: application/json' \
  -d '{"to_status": "closed", "outcome_note": "Reviewed, routine follow-up."}'

# 9. Share with the clinician, then export and delete.
curl -s -X POST $BASE/consent -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"scope": "share_with_clinician", "granted": true}'
curl -s $BASE/export -H "$AUTH" | python3 -m json.tool | head -30
curl -s -X DELETE $BASE/me -H "$AUTH"
```

The journey above mirrors the tested flows in `tests/unit/`; every step
there asserts the same status codes and bodies.
