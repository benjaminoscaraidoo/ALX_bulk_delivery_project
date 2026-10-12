# Bulk Delivery Ordering API

A **RESTful backend service for managing deliveries, packages, and payments** built with **Django** and **Django REST Framework (DRF)**.
The API supports role-based access for **drivers, customers, and administrators**, and provides comprehensive API documentation using **Swagger via drf-spectacular**.

---

## 🚀 Features

* User role management (Customer, Driver, Admin)
* Delivery creation and tracking
* Driver delivery status updates
* Delivery filtering, searching, and ordering
* Payment management
* Role-based permissions
* Atomic transaction handling for critical operations
* JWT authentication
* Fully interactive API documentation with Swagger

---

## 🧰 Technology Stack

* **Python**
* **Django**
* **Django REST Framework**
* **drf-spectacular** (Swagger / OpenAPI documentation)
* **django-filter**
* **SimpleJWT** for authentication

---

## 📁 Project Structure

```
project_root/
│
├── manage.py
│
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
│
├── core/
│   ├── schema.py
│   └── utilities and shared logic
│
├── delivery/
│   ├── models.py
│   ├── serializers.py
│   ├── filters.py
│   ├── views.py
│   └── urls.py
│
├── customer/
│   └── permissions.py
│
└── requirements.txt
```

---

## 🔐 Authentication

The API uses **JWT authentication**.

Clients must include the access token in requests:

```
Authorization: Bearer <access_token>
```

---

## 📦 Delivery Endpoints

### Search Deliveries

```
GET /v1/search/delivery/
```

Returns deliveries filtered based on the user's role.

**Query Parameters**

| Parameter       | Description                                |
| --------------- | ------------------------------------------ |
| search          | Search deliveries by id, address, or notes |
| ordering        | Sort results                               |
| delivery_status | Filter by delivery status                  |

Example:

```
GET /v1/search/delivery/?search=mall&ordering=-assigned_at
```

---

### Create Deliveries

```
POST /v1/delivery/create/
```

Creates one or more deliveries for packages.

**Example Request**

```json
{
  "deliveries": [
    {
      "package_id": "PKGE68...",
      "address": "Accra Mall Gate 2"
    },
    {
      "package_id": "PKGF79...",
      "address": "Sakaman Junction"
    }
  ]
}
```

**Example Response**

```json
{
  "detail": "2 deliveries created successfully.",
  "delivery_ids": [
    "DEL4D7...",
    "DEL5A7..."
  ]
}
```

---

### Driver Update Delivery

```
PUT /v1/delivery/update/
```

Allows a driver to update the status of a delivery.

**Example Request**

```json
{
  "package_id": "PKGE68...",
  "delivery_status": "picked_up"
}
```

**Example Response**

```json
{
  "Delivery_id": "DEL982...",
  "Delivery Status": "picked_up"
}
```

---

## 🔎 Filtering, Searching, and Ordering

The delivery list endpoint supports:

* **Filtering**
* **Search**
* **Ordering**

Example queries:

```
/v1/search/delivery/?delivery_status=picked_up
```

```
/v1/search/delivery/?search=mall
```

```
/v1/search/delivery/?ordering=-assigned_at
```

---

## 📘 API Documentation

The API documentation is automatically generated using **drf-spectacular**, which produces an **OpenAPI-compliant schema** and interactive Swagger UI.

### Swagger UI

```
/api/docs/
```

### OpenAPI Schema

```
/api/schema/
```

### ReDoc Documentation

```
/api/redoc/
```

These interfaces allow developers to:

* Explore all endpoints
* Test API requests directly in the browser
* View request/response schemas
* Inspect authentication requirements
* Understand filtering and query parameters

---

## ⚙️ Installation

### 1️⃣ Clone the repository

```
git clone https://github.com/benjaminoscaraidoo/ALX_bulk_delivery_project.git
cd ALX_bulk_delivery_project
```

### 2️⃣ Create a virtual environment

```
python -m venv venv
```

Activate it:

Linux/Mac:

```
source venv/bin/activate
```

Windows:

```
venv\Scripts\activate
```

---

### 3️⃣ Install dependencies

```
pip install -r requirements.txt
```

---

### Configure the environment

Copy `.env.example` to `.env` and set a newly generated `DJANGO_SECRET_KEY` and your email credentials. Do not reuse the secret previously committed to this repository. Replacing the deployed secret invalidates existing signed tokens and sessions.

Administrator accounts are created only on the server:

```
python manage.py createsuperuser
```

Public registration accepts only customers and drivers. Registration and password-reset confirmation tokens expire after five minutes, are single-use, and cannot be used as API access tokens.

### 4️⃣ Run migrations

```
python manage.py migrate
```

---

### 5️⃣ Start the server

```
python manage.py runserver
```

---

## 🧪 Running the API

Once the server starts, access:

```
https://benjaminoscaraidoo.pythonanywhere.com/api/docs/
```

to explore the API documentation.

---

## 🛠 Custom Schema

The project uses a **custom OpenAPI schema configuration** to automatically organize endpoints by application module.

Example:

```
core/schema.py
```

This custom schema extends the default schema generation to improve API documentation grouping and readability.

---

## 🧩 Permissions

Custom permissions enforce role-based access:

* **IsDriver**
* **IsAssignedDriverOrAdmin**
* **IsDriverProfileComplete**
* **IsCustomerProfileComplete**

These ensure that only authorized users can perform specific operations.

---

## 📈 Future Improvements

* Real-time delivery tracking
* SMS or push notifications for delivery updates
* Payment gateway integration
* Admin dashboard
* Driver route optimization

---

## 👤 Author

Oscar Aidoo

Backend Developer specializing in:

* Django
* Django REST Framework
* Banking systems integrations
* API architecture

---

## 📄 License

This project is licensed under the MIT License.


## Delivery pricing and payments

Run `python manage.py migrate` to install editable tariffs and the initial destination areas. In Django admin, manage **Distance tariffs** and **Delivery areas**. Kumasi, Takoradi and Tamale start without prices; set their charges before using automatic area pricing. Brackets initially charge GHS 35 up to 10 km, GHS 50 over 10–25 km, and GHS 60 over 25–30 km. Routes above the highest enabled bracket require an administrator quote.

Configure `GOOGLE_MAPS_API_KEY` privately and enable Google Maps Routes API on its project. Local quotes use driving distance from the order pickup address to the package `delivery_address`. Outside-Accra packages use the selected area's fixed tariff. Missing credentials or routing failures return an error instead of a guessed price. Existing quotes preserve their original charges when tariffs change. `total_price` is the sum of quoted packages; check `pricing_complete` before treating it as the final order total.

Use `GET /api/v1/pricing/areas/` to select an outside-Accra destination. Create packages with `delivery_address`, `outside_accra`, and `delivery_area` (required only when outside Accra). Use `POST /api/v1/package/quote/` with `package_id` to obtain a quote. For routes requiring a manual quote, staff may supply `amount` and `reason` to the same endpoint.

Create a pending payment with `POST /api/v1/payment/create/`, providing `package_id` and `payment_method` (`cash` or `mobile_money`). The amount comes from the quote. The assigned driver confirms cash through `POST /api/v1/payment/<id>/confirm/`; staff administrators confirm mobile money using that endpoint with `transaction_reference`. Customers cannot mark payments as paid. Use `GET /api/v1/search/payment/` to list payments visible to the logged-in user. Payment-provider integration is reserved for a later release.

Existing packages need delivery addresses before quotes can be generated. Existing payment records retain their current state. These changes do not create charges for legacy orders automatically.


## Django frontend

The frontend lives in the `frontend` app. Open `/` for the role-specific dashboard, `/login/` to sign in, `/register/` to create a customer or driver account, and `/password-reset/` to reset a password. Administrators are created through `python manage.py createsuperuser`. Profile completion is available at `/profile/`.

Customers can create orders, add packages, obtain quotes, create deliveries, and choose payment methods. Drivers can update assigned orders and confirm cash. Staff can approve drivers, assign orders, set manual quotes, and confirm mobile money. Tariffs remain in Django admin.

Pages use Django session login and call existing APIs with CSRF-protected requests. JWT authentication remains available to other API clients. For a local preview with `DEBUG=False`, use `python manage.py runserver --insecure` so static CSS and JavaScript are served. Production deployment must serve collected static files separately; `--insecure` is only for local development.

For mobile money, the assigned driver or a staff administrator can save the MoMo transaction ID on the order page. The payment stays pending until staff confirms receipt. The admin confirmation form pre-fills the saved ID. The API endpoint is `POST /api/v1/payment/<id>/reference/`, accepting `transaction_reference`; the payment response includes `transaction_recorded_by` and `transaction_recorded_at`.

Profile completion is recalculated after every profile update. Customer completion requires a name and address; driver completion requires vehicle type, vehicle number and license number. Duplicate customer phone numbers return validation errors, and user/profile changes save together. Editing vehicle or license details resets driver approval to pending and blocks new assignments; existing assigned deliveries remain accessible when the profile is complete. Name and availability changes do not reset approval.


## Concurrent writes

SQLite transactions use `IMMEDIATE` mode with a 20-second lock timeout. Busy/locked API writes return a generic 503 response with `Retry-After: 1`. Delivery creation locks orders in a consistent order and rechecks ownership, state and the current driver before saving. OTP replacement, verification and confirmation coordinate on the user record; email sending occurs after the replacement transaction commits.

Run simultaneous-request tests against an isolated disk-backed database, for example:

```
SQLITE_TEST_DATABASE=/tmp/parcel-concurrency-test.sqlite3 python manage.py test --noinput
```

Use a disposable path: the test runner creates and removes this database. Default in-memory SQLite cannot reproduce normal file-lock waiting, so the concurrency test class skips in-memory runs. These tests cover overlapping requests, not production load capacity. SQLite still serializes writes; larger deployment capacity requires a separate database decision.


## Production deployment

See [the deployment guide](docs/deployment.md) for PythonAnywhere configuration, backups, migrations, static files, tariff setup and verification. Set `DJANGO_ENV=production` and explicit `DJANGO_ALLOWED_HOSTS` on the server. Production enables HTTPS redirects and secure session/CSRF cookies; local preview remains HTTP-compatible. Trust forwarded HTTPS headers only with `DJANGO_TRUST_PROXY=True` after verifying the host's proxy configuration. HSTS starts at one hour without preload or subdomain enforcement.
