# smarthr360-policy-gen

**AI HR policy generator microservice of the SmartHR360 platform
(Module 4).** The strategic module: analyzes internal social data
(turnover, performance, retention), simulates the impact of HR policies
(raise, remote work, training, wellness, flexible hours, mentorship)
and generates prioritized recommendations with a Groq LLM — with a
deterministic static fallback when no LLM is configured.

Part of [SmartHR360](https://github.com/NawfalRAZOUK7/smarthr360).
Rescued from the never-merged `Module-4-update` branch of the legacy
shared repo and converted from a template UI to REST APIs.

## API

| Endpoint | Role | Purpose |
|---|---|---|
| `GET /api/policy/analytics/` | HR | turnover %, avg performance, retention stats |
| `POST /api/policy/simulate/` `{policy_type, magnitude 0-10}` | HR | predicted impact (turnover/performance/cost) |
| `GET /api/policy/recommendations/?budget=` | HR | AI proposals sorted by cost |
| `POST /api/policy/apply/` | HR | apply a policy (demo semantics) |
| `POST /api/policy/demo-data/reset/` | HR | reseed the analytical store |

Identity: RS256 JWT from smarthr360-auth (local verification).

## Notes

- The local Employe/PerformanceReview tables are this service's
  **analytical store** (demo-seeded). Feeding them from core-hr
  aggregates is a v2 item (event pipeline).
- `GROQ_API_KEY` via env only. Without it every endpoint still works
  through the static logic (tests run Groq-less).

## Quickstart

```bash
pip install -r requirements.txt && cp .env.example .env
python manage.py migrate && python manage.py populate_demo_data
python manage.py runserver 0.0.0.0:8006
```

Tests: `python manage.py test` (6 tests)
