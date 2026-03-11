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
cd bulk-delivery-api
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
