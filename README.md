# ShopAssist AI application

A full-stack, runnable companion to the CCAR-F-Main course material. It turns the course's
canonical ShopAssist tools into a practical customer-support console with a FastAPI backend and
a React frontend.

The console uses Claude tool calling for the conversational workflow. Claude chooses which
ShopAssist operation to investigate and writes the reply, while the backend remains the source
of truth for ownership, refund policy, and actions. Read the full
[architecture and workflow](ARCHITECTURE.md), including diagrams and MCP setup.

## Practical use cases included

- Verify a customer by email before accessing account data.
- Verify ownership before looking up an order.
- Process eligible damaged-item, missing-item, wrong-item, and duplicate-charge refunds.
- Enforce a delivered-within-30-days policy in the backend.
- Create a concise human-support escalation for policy exceptions.
- Show the tool-by-tool audit trail to the support agent/customer.

The demo accounts deliberately reuse the course fixtures:

| Email | Customer ID | Order | Example outcome |
| --- | --- | --- | --- |
| `alex@example.com` | `CUS-1001` | `ORD-12345678` | Refund: delivered 12 days ago |
| `alex@example.com` | `CUS-1001` | `ORD-87654321` | Escalation: delivered 45 days ago |

## Run it

Open two terminals from this directory.

```bash
# Terminal 1: API and interactive Swagger documentation
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Create ../../.env with ANTHROPIC_API_KEY=... for the AI workflow.
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI and
[http://localhost:8000/redoc](http://localhost:8000/redoc) for ReDoc.

```bash
# Terminal 2: React support console
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## API map

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/customers/lookup` | Verify customer identity from email |
| `POST` | `/api/orders/lookup` | Retrieve an order after ownership verification |
| `POST` | `/api/refunds/eligibility` | Check the service-enforced return policy |
| `POST` | `/api/refunds` | Submit an eligible refund |
| `POST` | `/api/escalations` | Route exceptions to a human specialist |
| `POST` | `/api/cases/resolve` | Run the complete deterministic guided workflow |
| `POST` | `/api/chat` | Run Claude's tool-calling support workflow |

## Validation

```bash
cd backend
pytest
```

The deterministic endpoint is useful for tests and no-key demos. The React console uses
`/api/chat`, which runs the real Claude tool-use loop. See [ARCHITECTURE.md](ARCHITECTURE.md)
for the run instructions, MCP server command, and production safeguards.
