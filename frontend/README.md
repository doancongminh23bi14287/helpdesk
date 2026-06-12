# WorkDesk

A production-ready client support and workload management frontend built on Vite + React.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Vite + React + Tailwind CSS + Heroicons |
| State | Zustand (auth) + React hooks |
| API | Axios → Frappe REST API |
| Backend | ERPNext + Frappe Helpdesk + custom Frappe App |

---

## Project Structure

```
customer-portal/
├── src/
│   ├── components/
│   │   ├── ui/          # Badge, Button, Card, Input, Spinner, etc.
│   │   └── layout/      # Layout (sidebar), ProtectedRoute
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── DashboardPage.jsx
│   │   ├── TicketListPage.jsx
│   │   ├── NewTicketPage.jsx
│   │   ├── TicketDetailPage.jsx
│   │   ├── ServicesPage.jsx
│   │   └── NotificationsPage.jsx
│   ├── services/
│   │   └── api.js        # Axios wrapper for all ERPNext/Helpdesk calls
│   ├── hooks/
│   │   ├── useAuth.js    # Zustand auth store
│   │   ├── useTickets.js # Ticket data hooks
│   │   └── useServices.js
│   └── lib/
│       └── utils.js      # cn(), formatDate(), daysUntil()
│
└── backend/
    └── customer_portal/  # Frappe custom app
        ├── api/
        │   └── __init__.py   # All @frappe.whitelist() endpoints
        ├── hooks/
        │   └── ticket_hooks.py
        ├── tasks.py          # Scheduled jobs
        └── hooks.py          # App configuration
```

---

## Frontend Setup

```bash
cd customer-portal
npm install
npm run dev          # Dev server on :5173, proxies /api → localhost:8000
npm run build        # Production build → dist/
```

### Serve built files via Nginx (alongside ERPNext)

```nginx
server {
    listen 80;
    server_name portal.yourdomain.com;

    root /path/to/customer-portal/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Backend Setup

```bash
# From your Frappe bench directory
bench get-app /path/to/customer-portal/backend/customer_portal
bench --site yoursite.com install-app customer_portal
bench --site yoursite.com migrate
```

### Required DocTypes

The app uses these DocTypes out of the box:
- `HD Ticket` — Frappe Helpdesk
- `HD Ticket Comment` — Frappe Helpdesk  
- `Subscription` — ERPNext

**Optional custom DocType: `Hosting Plan`**

Create via Frappe UI with fields:
| Field | Type |
|-------|------|
| customer | Link → Customer |
| plan | Data |
| domain | Data |
| status | Select: Active/Inactive/Cancelled |
| expiry_date | Date |
| disk_usage | Data |
| monthly_cost | Currency |

---

## API Reference

### Auth
```
POST /api/method/login           { usr, pwd }
GET  /api/method/logout
GET  /api/method/frappe.auth.get_logged_user
```

### Tickets (Frappe Helpdesk)
```
GET  /api/resource/HD Ticket
GET  /api/resource/HD Ticket/:id
POST /api/resource/HD Ticket
GET  /api/resource/HD Ticket Comment?filters=[["reference_ticket","=","HD-TICKET-00001"]]
POST /api/method/customer_portal.api.reply_to_ticket   { ticket_id, message }
```

### Services (Custom)
```
GET  /api/method/customer_portal.api.get_customer_services
GET  /api/method/customer_portal.api.get_portal_summary
```

---

## Environment / CORS

During development, Vite proxies all `/api` calls to `http://localhost:8000`.

For production, configure Frappe's `common_site_config.json`:
```json
{
  "allow_cors": "https://portal.yourdomain.com"
}
```

---

## Email Piping (Incoming Email → Ticket)

In ERPNext → **Email Account**, create an account with:
- **Enable Incoming**: ✅
- **Append To**: `HD Ticket`
- **Frappe Helpdesk** will automatically create tickets from incoming emails.
