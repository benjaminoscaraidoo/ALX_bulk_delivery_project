Bulk Delivery Ordering Platform (Django)

A multi-package delivery platform built with Django, designed for logistics companies where:
    Customers create orders
    Each order contains multiple packages
    Each package has its own delivery address
    Drivers/Riders are automatically assigned
    Admins manage everything via a dashboard

This project uses session-based authentication for HTML pages and JWT for APIs, following best industry practices.

🚀 Features Implemented
✅ Authentication & Security

Custom user model with roles:
    Customer
    Driver
    admin

Django session authentication for HTML pages
JWT authentication for API endpoints
CSRF protection enabled
Auto logout after inactivity (django-auto-logout)
Role-based access control