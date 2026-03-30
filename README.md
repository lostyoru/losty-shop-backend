# 🛍️ LostyShop — Django Backend

> **A production-grade, multi-role e-commerce API** built with Django REST Framework, Django Channels (WebSocket), and Stripe — designed to power a full-featured online marketplace.

---

## 📑 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Architecture](#project-architecture)
- [Applications (Apps)](#applications-apps)
- [Role-Based Access Control](#role-based-access-control)
- [Authentication System](#authentication-system)
- [API Features](#api-features)
- [Payment Integration (Stripe)](#payment-integration-stripe)
- [Real-Time Communication](#real-time-communication)
- [API Documentation](#api-documentation)
- [Environment Variables](#environment-variables)
- [Getting Started](#getting-started)
- [Database Schema (Overview)](#database-schema-overview)

---

## Overview

**LostyShop** is a full-stack e-commerce backend serving three distinct actor types — **Buyers (Users)**, **Sellers**, and **Admins** — each with their own authentication flow, data scope, and access permissions. The backend exposes a RESTful API, handles secure payment via **Stripe**, manages product catalogs and order lifecycle, and delivers real-time notifications via WebSockets.

---

## Tech Stack

| Category              | Technology                                               |
| --------------------- | -------------------------------------------------------- |
| **Framework**         | Django 5.2 + Django REST Framework 3.15                  |
| **ASGI Server**       | Daphne 4.1                                               |
| **Real-Time**         | Django Channels 4.2 + channels-redis 4.2                 |
| **Database**          | PostgreSQL (via psycopg2)                                |
| **Authentication**    | JWT (djangorestframework-simplejwt) + Google OAuth (allauth) |
| **2FA**               | TOTP via pyotp + QR Code (qrcode)                        |
| **Payments**          | Stripe (stripe-python SDK)                               |
| **Media Storage**     | Cloudinary                                               |
| **Admin Panel**       | Django Unfold                                            |
| **API Schema**        | drf-spectacular (OpenAPI 3 / Swagger / Redoc)            |
| **Permissions**       | Custom DRF Permission Classes + django-guardian           |
| **Encryption**        | Fernet (cryptography) for 2FA secret storage             |
| **Email**             | Django SMTP Backend                                      |
| **Filtering**         | django-filter + DRF SearchFilter + OrderingFilter        |

---

## Project Architecture

The backend follows **Django's idiomatic app-based architecture**. Each domain is encapsulated in its own Django application, keeping concerns separated and the codebase scalable.

```
losty-py/
├── config/                  # Django project config (settings, URLs, ASGI/WSGI)
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── core/                    # Shared utilities, permissions, backends, adapters
│   ├── permissions.py       # Custom DRF permission classes (IsUser, IsSeller, IsAdmin)
│   ├── backends.py          # MultiEntityJWTAuthentication backend
│   ├── adapters.py          # Custom allauth account adapter
│   ├── admin.py             # Unfold admin registrations
│   └── utils/               # Cloudinary, email utilities
│
├── accounts/                # User, Seller, Admin models + auth endpoints
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── catalog/                 # Product, Category, Review management
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── orders/                  # Orders, OrderItems, Payments + Stripe webhooks
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   └── urls.py
│
├── communications/          # Real-time chat, notifications (WebSocket + REST)
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── consumers.py         # WebSocket consumer (Channels)
│   ├── routing.py
│   └── urls.py
│
├── manage.py
├── requirements.txt
└── .env.example
```

### Key Architectural Patterns

- **Multi-Entity JWT Authentication** — A single custom DRF authentication backend (`MultiEntityJWTAuthentication`) resolves tokens for three distinct entity tables (`users`, `sellers`, `admins`) by reading the `userType` claim embedded in the JWT payload.
- **Role-Scoped ViewSets** — Each ViewSet inspects `request.auth_user_type` to scope database queries and enforce permissions without relying on Django's built-in `is_staff` / `is_superuser` alone.
- **ASGI-first** — The project runs under Daphne with ASGI, enabling HTTP and WebSocket connections on the same server.

---

## Applications (Apps)

### `accounts` — Identity & Authentication
Manages all three actor types and their authentication flows.

**Models:**
- `User` — Buyer accounts. Extends `AbstractBaseUser`. Supports email/password, Google OAuth, and 2FA.
- `Seller` — Merchant accounts with a unique `store_name`, storefront description, and product ownership.
- `Admin` — Platform administrator accounts with username-based identity.

**Endpoints:**

| Method | Path | Description | Access |
|--------|------|-------------|--------|
| `POST` | `/api/accounts/register/user/` | Register a buyer | Public |
| `POST` | `/api/accounts/register/seller/` | Register a seller | Public |
| `POST` | `/api/accounts/register/admin/` | Register an admin | Public |
| `POST` | `/api/accounts/login/` | Unified login (user/seller/admin) | Public |
| `POST` | `/api/accounts/logout/` | Invalidate refresh token | Authenticated |
| `POST` | `/api/accounts/verify-2fa/` | Complete 2FA login step | Public |
| `POST` | `/api/accounts/2fa/generate/` | Generate TOTP QR code | Authenticated |
| `POST` | `/api/accounts/2fa/enable/` | Enable 2FA after verification | Authenticated |
| `POST` | `/api/accounts/2fa/disable/` | Disable 2FA | Authenticated |
| `GET`  | `/api/accounts/social-session/` | Exchange Google session for JWT | Public |
| `GET`  | `/api/accounts/users/profile/` | Get own buyer profile | User only |
| `PATCH`| `/api/accounts/users/profile-update/` | Update buyer profile | User only |
| `POST` | `/api/accounts/users/change-password/` | Change buyer password | User only |
| `POST` | `/api/accounts/users/avatar/` | Upload buyer avatar | User only |
| `GET`  | `/api/accounts/sellers/profile/` | Get own seller profile | Seller only |
| `PATCH`| `/api/accounts/sellers/profile-update/` | Update seller profile | Seller only |
| `POST` | `/api/accounts/sellers/avatar/` | Upload seller avatar | Seller only |
| `GET`  | `/api/accounts/sellers/public/` | List all public seller profiles | Public |
| `GET`  | `/api/accounts/sellers/{id}/store/` | Seller storefront with products | Public |
| `GET`  | `/api/accounts/auth/google/login/` | Initiate Google OAuth | Public |

---

### `catalog` — Product & Category Management
Handles the full product lifecycle: creation, editing, image management, categorization, and reviews.

**Models:**
- `Category` — Product categories (Admin-managed).
- `Product` — Listed by a `Seller`. Includes name, description, price, stock, images (stored on Cloudinary), and active status.
- `Review` — Left by a `User` on a `Product`. One review per user per product enforced at DB level.

**Endpoints:**

| Method | Path | Description | Access |
|--------|------|-------------|--------|
| `GET` | `/api/catalog/categories/` | List all categories | Public |
| `POST` | `/api/catalog/categories/` | Create category | Admin only |
| `PUT/PATCH` | `/api/catalog/categories/{id}/` | Update category | Admin only |
| `DELETE` | `/api/catalog/categories/{id}/` | Delete category | Admin only |
| `GET` | `/api/catalog/products/` | List products (filter, search, sort) | Public |
| `GET` | `/api/catalog/products/{id}/` | Product detail | Public |
| `POST` | `/api/catalog/products/` | Create product + upload images | Seller only |
| `PATCH` | `/api/catalog/products/{id}/` | Update product / manage images | Seller only |
| `DELETE` | `/api/catalog/products/{id}/` | Delete product + Cloudinary cleanup | Seller only |
| `GET` | `/api/catalog/products/seller-products/` | Seller's own products | Seller only |
| `GET` | `/api/catalog/products/{id}/reviews/` | List reviews for a product | Public |
| `POST` | `/api/catalog/products/{id}/reviews/` | Leave a review | User only |
| `PATCH` | `/api/catalog/products/{id}/reviews/{id}/` | Edit own review | User only |
| `DELETE` | `/api/catalog/products/{id}/reviews/{id}/` | Delete own review | User only |

**Image management features:**
- Multi-file upload via `MultipartParser`
- Cloudinary CDN upload on create/update
- Orphaned image cleanup on product update/delete
- `mainImage` pinning (first image in array = display thumbnail)

---

### `orders` — Orders, Cart Checkout & Payments
Manages the full order and payment lifecycle, from placing an order to payment confirmation and shipping.

**Models:**
- `Order` — Links a `User` (buyer) and a `Seller`. Tracks status (`PENDING → PAID → SHIPPED → DELIVERED → CANCELLED`), total amount, and shipping address.
- `OrderItem` — Individual line items of an order with price snapshotted at purchase time.
- `Payment` — Linked 1-to-1 with an Order. Tracks Stripe session IDs, checkout URL, and payment status (`PENDING / SUCCESS / FAILED`).

**Endpoints:**

| Method | Path | Description | Access |
|--------|------|-------------|--------|
| `GET` | `/api/orders/` | List own orders | User / Seller |
| `POST` | `/api/orders/` | Place new order (decrements stock) | User / Seller |
| `GET` | `/api/orders/{id}/` | Order detail | Authenticated |
| `POST` | `/api/orders/{id}/confirm/` | Mark order as paid (manual) | Seller only |
| `POST` | `/api/orders/{id}/ship/` | Mark order as shipped | Seller only |
| `POST` | `/api/orders/checkout/` | Create Stripe payment session | User / Seller |
| `POST` | `/api/orders/webhook/stripe/` | Stripe webhook handler | Public (signed) |

**Notes:**
- Multi-seller orders are automatically split into per-seller sub-orders at the time of checkout.
- Stock is atomically decremented on order creation.
- Sellers can optionally view orders where they are the buyer using `?scope=buyer`.

---

### `communications` — Chat & Notifications
Provides real-time in-app messaging and a notification system using Django Channels and WebSockets.

**Models:**
- `ChatMessage` — Stores messages between any combination of `User ↔ User`, `User ↔ Seller`, or `Seller ↔ Seller`. Uses UUID foreign keys for sender/receiver with explicit type strings for cross-table resolution.
- `Notification` — Persistent per-recipient notification records with type, title, message, read status, and arbitrary `metadata` JSON.

**REST Endpoints:**

| Method | Path | Description | Access |
|--------|------|-------------|--------|
| `POST` | `/api/communications/chat/send/` | Send a message | User / Seller |
| `GET` | `/api/communications/chat/conversations/` | List all conversations with partner info | User / Seller |
| `GET` | `/api/communications/chat/conversation/{partner_id}/` | Full message thread with a partner | User / Seller |
| `POST` | `/api/communications/chat/mark-read/` | Mark messages as read | User / Seller |
| `GET` | `/api/communications/notifications/` | List notifications (paginated) | Authenticated |
| `POST` | `/api/communications/notifications/mark-read/` | Mark specific notifications read | Authenticated |
| `POST` | `/api/communications/notifications/mark-all-read/` | Mark all notifications read | Authenticated |
| `GET` | `/api/communications/notifications/unread-count/` | Get unread count | Authenticated |

**WebSocket:**

```
ws://<host>/ws/notifications/?token=<JWT_ACCESS_TOKEN>
```

| Event (server → client) | Description |
|--------------------------|-------------|
| `unreadCount` | Sent on connect with current unread count |
| `notification` | Pushed on new message or system event |

| Command (client → server) | Description |
|---------------------------|-------------|
| `markAsRead` | Mark notification IDs as read; returns updated count |

---

## Role-Based Access Control

LostyShop enforces strict role-based access via a custom **Multi-Entity JWT** system and four DRF permission classes defined in `core/permissions.py`.

### Roles

| Role | Entity Table | Description |
|------|-------------|-------------|
| `user` | `accounts_users` | Buyer. Can browse, purchase, review, and chat. |
| `seller` | `accounts_sellers` | Merchant. Can manage products, view/ship orders, and chat. |
| `admin` | `accounts_admins` | Platform admin. Manages categories and has Django admin access. |

### Permission Classes

| Class | Grants Access To |
|-------|-----------------|
| `IsUser` | Authenticated tokens with `userType == "user"` |
| `IsSeller` | Authenticated tokens with `userType == "seller"` |
| `IsAdmin` | Authenticated tokens with `userType == "admin"` |
| `IsUserOrSeller` | Either `"user"` or `"seller"` token types |

### How the JWT-based identity works

1. On login, the backend generates a JWT pair (`accessToken` + `refreshToken`).
2. Both tokens carry a `userType` claim (`"user"` / `"seller"` / `"admin"`) and a `sub` claim (entity UUID).
3. `MultiEntityJWTAuthentication` (in `core/backends.py`) decodes the token, reads `userType`, and fetches the correct entity from the correct table.
4. The resolved entity is attached to `request.auth_entity`; the type is attached to `request.auth_user_type`.
5. Permission classes check `request.auth_user_type` to grant or deny access.

### Role Capabilities Summary

| Capability | User | Seller | Admin |
|-----------|:----:|:------:|:-----:|
| Browse products & categories | ✅ | ✅ | ✅ |
| Register / Login / OAuth | ✅ | ✅ | ✅ |
| 2FA (TOTP) | ✅ | ✅ | ❌ |
| Manage own profile & avatar | ✅ | ✅ | ❌ |
| Leave product reviews | ✅ | ❌ | ❌ |
| Place orders | ✅ | ✅ (as buyer) | ❌ |
| Pay via Stripe | ✅ | ✅ (as buyer) | ❌ |
| Create / update products | ❌ | ✅ | ❌ |
| Upload product images | ❌ | ✅ | ❌ |
| View & manage own orders | ❌ | ✅ | ❌ |
| Mark orders as shipped | ❌ | ✅ | ❌ |
| Manage categories | ❌ | ❌ | ✅ |
| Access Django Admin panel | ❌ | ❌ | ✅ |
| Send / receive chat messages | ✅ | ✅ | ❌ |
| Receive real-time notifications | ✅ | ✅ | ❌ |

---

## Authentication System

### Email & Password
- Users register and log in with email + hashed password.
- Sellers and Admins follow the same email-based flow but are stored in separate tables.
- Passwords are hashed using Django's `make_password` / `check_password` (PBKDF2).
- Refresh tokens are hashed and stored per-entity; logout nullifies the stored hash.

### Google OAuth (Users only)
- Implemented via `django-allauth` + `dj-rest-auth`.
- On successful Google sign-in, the session is exchanged for API JWT tokens via `GET /api/accounts/social-session/`.
- Configured via `SOCIALACCOUNT_PROVIDERS` with `client_id` and `secret` from Google Cloud Console.

### Two-Factor Authentication (TOTP)
- Available for `user` and `seller` accounts.
- Secrets are encrypted with **Fernet (AES-256)** before being stored in the database.
- Flow:
  1. `POST /2fa/generate/` → Returns a QR code (base64 PNG) and TOTP secret.
  2. User scans QR code with an authenticator app (e.g., Google Authenticator).
  3. `POST /2fa/enable/` → Verifies first code; enables 2FA on the account.
  4. On next login, if 2FA is enabled, the API returns `requires2FA: true`.
  5. `POST /verify-2fa/` → Verifies TOTP code and returns full JWT pair.

### JWT Token Strategy
- **Access Token** — Short-lived (default: 60 minutes). Sent as `Bearer` header.
- **Refresh Token** — Long-lived (default: 7 days). Stored hashed in the database to allow server-side logout.
- Both tokens embed `userType` and `sub` (entity UUID) as custom claims.

---

## Payment Integration (Stripe)

LostyShop uses **Stripe** as its payment gateway for secure, international card payments.

### Flow

```
User/Seller → POST /api/orders/checkout/
    ↓
Backend creates a Stripe Checkout Session
    ↓
Returns { checkoutUrl }
    ↓
Client redirects to Stripe's hosted checkout page
    ↓
User completes payment on Stripe
    ↓
Stripe sends POST /api/orders/webhook/stripe/ (signed)
    ↓
Backend verifies signature → updates Payment to SUCCESS
    ↓
Order status updated to PAID
    ↓
Purchase confirmation email sent to buyer
```

### Stripe Configuration

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Your Stripe secret key (`sk_live_...` or `sk_test_...`) |
| `STRIPE_PUBLISHABLE_KEY` | Your Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (`whsec_...`) for signature verification |

### Webhook Security
All incoming Stripe webhooks are verified using `stripe.Webhook.construct_event()` with the webhook signing secret — ensuring that only genuine Stripe events are processed.

### Stripe Checkout Session
- Payment method: **Card**
- Currency: **USD**
- Session references the `order.id` via `client_reference_id` for webhook reconciliation.
- Success and cancel URLs are dynamically configured from `FRONTEND_URL`.

---

## Real-Time Communication

Django Channels powers the WebSocket layer, served via **Daphne** (ASGI).

- **Channel Layer**: Redis (production) or In-Memory (development). Controlled by the `USE_REDIS_CHANNEL_LAYER` environment variable.
- **Consumer**: `NotificationConsumer` handles WebSocket connections, authenticates via JWT passed as a query parameter (`?token=...`), and joins per-user channel groups.
- **Push notifications**: When a chat message is sent, the backend pushes a `NEW_MESSAGE` event directly to the receiver's channel group via `channel_layer.group_send`.
- **First-contact email**: When a buyer sends their first message to a seller, an email notification is dispatched to the seller.

---

## API Documentation

Interactive API documentation is auto-generated via **drf-spectacular**:

| Path | Description |
|------|-------------|
| `GET /api/schema/` | Raw OpenAPI 3 schema (YAML/JSON) |
| `GET /api/docs/` | Swagger UI |
| `GET /api/redoc/` | ReDoc UI |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
# Django
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
DB_NAME=lostyshop
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-chars
JWT_REFRESH_SECRET_KEY=your-super-secret-refresh-key-min-32-chars
JWT_ACCESS_TOKEN_LIFETIME_MINUTES=60
JWT_REFRESH_TOKEN_LIFETIME_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_CALLBACK_URL=http://localhost:8000/api/accounts/auth/google/callback

# Cloudinary
CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret

# Stripe
STRIPE_SECRET_KEY=sk_test_your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-publishable-key
STRIPE_WEBHOOK_SECRET=whsec_your-stripe-webhook-secret

# SMTP
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password

# Redis (for WebSocket channel layer)
REDIS_HOST=localhost
REDIS_PORT=6379
USE_REDIS_CHANNEL_LAYER=False   # Set to True in production

# Encryption (32-character key for AES-256/Fernet)
ENCRYPTION_KEY=12345678901234567890123456789012

# URLs
FRONTEND_URL=http://localhost:5173
BACKEND_URL=http://localhost:8000
PORT=8000
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis (optional for dev, required for production WebSockets)

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd losty-py

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Fill in .env with your actual values

# 5. Run database migrations
python manage.py migrate

# 6. Create a superuser (Admin)
python manage.py createsuperuser

# 7. Start the development server (ASGI via Daphne)
daphne -p 8000 config.asgi:application

# Or with Django's default dev server (no WebSocket support):
python manage.py runserver
```

### Stripe Webhook (Development)

Use the Stripe CLI to forward webhooks to your local server:

```bash
stripe listen --forward-to http://localhost:8000/api/orders/webhook/stripe/
```

---

## Database Schema (Overview)

```
users ──────────────────┐
                        │ FK (buyer)
sellers ─────────────── orders ──── order_items ──── products ──── categories
          FK (seller)       │
                        payments
                        
users ─────── reviews ─────── products

chat_messages (sender_id / receiver_id as generic UUIDs with type string)
notifications (recipient_id as generic UUID with type string)
```

**All primary keys** are UUIDs (`uuid4`), generated at the database level for security and distributed compatibility.

---

## License

This project is private and proprietary. All rights reserved © LostyShop 2026.
