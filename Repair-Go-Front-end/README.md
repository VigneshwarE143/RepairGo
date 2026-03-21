# RepairGo Frontend

Role-based React frontend for the RepairGo FastAPI backend.

## Stack

- React + Vite
- React Router
- Redux Toolkit
- Axios
- React Hook Form + Zod
- React Leaflet
- Recharts
- React Hot Toast

## Setup

1. Copy env file:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
npm install
```

3. Start dev server:

```bash
npm run dev
```

4. Build for production:

```bash
npm run build
```

## Environment

- `VITE_API_URL` = Backend base URL (default: `http://127.0.0.1:8000`)

## Main Features

- Auth: login/register, JWT localStorage, role-based redirects
- Customer: create request, estimate pricing, list/filter requests, rating modal, map tracking
- Technician: jobs dashboard, status workflow, location updates, cancel flow
- Admin: users/technicians/requests/revenue/fraud/background health dashboards

## Backend Endpoint Notes

The UI is wired to currently available endpoints. For missing endpoints (customer-specific requests, notifications list, profile update), the UI includes graceful placeholders so integration can be added without redesign.
