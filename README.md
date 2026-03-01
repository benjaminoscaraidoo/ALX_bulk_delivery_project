Bulk Delivery Ordering Platform (Django)

A RESTful API built with Django and Django REST Framework where:
    Customers create orders
    Each order contains multiple packages
    Each package has its own delivery address
    Drivers/Riders are automatically assigned
    Drivers/Riders can be manually assigned
    Status transitions
    Cancellation workflows
    Authentication (JWT ready)

Apps:
    customer
    order
    delivery

Models:
    customer: DriverProfile, CustomerProfile, CustomUser, EmailOTP
    delivery: Delivery, Payment
    order: Order, Package

Custom user model with roles:
    Customer
    Driver
    admin

🚀 Features
✅ Create & manage Orders
✅ Assign Packages to Orders
✅ Track Delivery status:
    assigned
    picked_up
    delivered
    cancelled
✅ Cancel orders with cascade update to deliveries
✅ Transaction-safe updates
✅ Role-based permissions (Admin, Driver, Customer,Authenticated users)
✅ Body-based API requests (no URL params for state changes)
✅ Atomic database operations

🧱 Tech Stack
Backend: Django
API Layer: Django REST Framework
Database: PostgreSQL / SQLite
Authentication: JWT (SimpleJWT compatible)
Transactions: transaction.atomic()


Architecture Flow:
    For Customers
    **********************
    Customer Register:
        >
        Complete Profile:
            >    
            Create Order:
                >
                Add Packages/Receiver Details:
                    >
                    Create Deliveries:
                        >
                        Update Receiver details if information is missing:
                            >
                            Cancel Order with valid reason


    For Drivers
    **********************
    Driver Register:
        >
        Complete Profile:
            >    
            Update delivery status(pickedup/delivered):


    Admin:
    ***********
    SuperUser Register:
        >
        Driver Approval:
            

Endpoints:
    Registration:
        Super User:
            POST /customer/api/v1/register_superuser/

            REQUEST JSON:
            {
                "email": "register.user@example.net",
                "phone_number": "0242848472",
                "first_name": "Ben",
                "last_name": "Aidoo",
                "password": "StrongPassword",
                "password2": "StrongPassword"
            }
        
        Customer/Driver:
            POST /customer/api/v1/register/request/

            REQUEST JSON:
            {
                "email": "registercus.user@example.net",
                "phone_number": "056554455",
                "role": "customer",
                "password": "StrongPassword",
                "password2": "StrongPassword"
            }

        OTP Verification:
            POST /customer/api/v1/register/verify/

            REQUEST JSON:
            {
                "email":"registercus.user@example.net"",
                "otp":"352163"
            }

        Token Confirmation:
            POST /customer/api/v1/register/confirm/

            REQUEST JSON:
            {
                "email":"benjamin.aidoo@brac.net",
                "register_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzcyMjk2MTMzLCJpYXQiOjE3NzIyOTQzMzMsImp0aSI6ImY5YjgxODdmMDAzYzRiOTk5N2FkNjQ4ZmU1ZWEyMzk0IiwidXNlcl9pZCI6IjE1Iiwic2NvcGUiOiJyZWdpc3RyYXRpb24ifQ.mK536oBGCKq1xeVL7XefjvBOcFsuB6a_U2T1uE-3ww4"
            }


    Login:
        POST /customer/api/v1/auth/login/

        REQUEST JSON:
        {
            "email":"userlogin@gmail.com",
            "password":"StrongPassword"
        }


    Token Refresh:
        POST /customer/api/v1/auth/token/refresh/

        REQUEST JSON:
            {
                "refresh":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTc3MjYzNjExMywiaWF0IjoxNzcyMDMxMzEzLCJqdGkiOiIyY2I5OTUxN2Q5YTc0MTdlYTYxMTE2Mzg5OWJkYjA5ZiIsInVzZXJfaWQiOiI2Iiwicm9sZSI6ImN1c3RvbWVyIn0.smZL4EU1oY7VElM4tmBTl0-leVv-LxtymHvsYSSnGyw"
            }


    Password Reset Request:
        POST /customer/api/v1/password-reset/request/

        REQUEST JSON:
            {
                "email":"passwordreset@gmail.com"
            }


    Password Reset OTP Verification:
        POST /customer/api/v1/password-reset/verify/

        REQUEST JSON:
           {
                "email": "benaidoojnr@gmail.com",
                "otp": "813176"
    
            }

    Password Rest Token Confirmation:
        POST /customer/api/v1/password-reset/confirm/

        REQUEST JSON:
            {
                "reset_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzcyMjA1NDQxLCJpYXQiOjE3NzIyMDM2NDEsImp0aSI6IjExNDUwZWIwMzhmYTRhNzE4YjU1YjFkMzRiYzBmYjAxIiwidXNlcl9pZCI6IjgiLCJzY29wZSI6InBhc3N3b3JkX3Jlc2V0In0.SaySCfI91KwYDHCRXNFESlYQyCknPV3a2gwirUUBNgg",
                "new_password": "StrongPassword"
            }


    Customer Profile Update:
        PUT /customer/api/v1/profile/update/

        REQUEST JSON:
            {
                "first_name": "Siato",
                "last_name": "Wanem",
                "phone_number": "0243424221",
                "address": "a567/16 Dama Street"
            }

    Driver Profile Update:
        PUT /customer/api/v1/profile/update/

        REQUEST JSON:
        {
            "first_name": "Issah",
            "last_name": "Mussah",
            "vehicle_type": "Royal Motor",
            "vehicle_number": "MT-1076-22",
            "license_number": "DV100188211222"
        }

    Driver Admin Approval:
        PUT /customer/api/v1/admin/driver/approve/

        REQUEST JSON:
        {
            "email": "asango@gmail.com",
            "action": "approve"
        }

    Order Creation:
        POST /order/api/v1/create/

        REQUEST JSON:
        {
            "pickup_address": "Ofankor barrier"
        }

    Cancel Order:
        PUT /order/api/v1/order/cancel/

        REQUEST JSON:
        {
            "order_id":"6",
            "cancel_reason":"Mistaken Order"
        }

    Order Driver Assignment:
        PUT /order/api/v1/order/assign/

        REQUEST JSON:
        {
            "order_id":"9",
            "driver_email":"asango@gmail.com" 
        }

    Search Orders:
        GET /order/api/v1/order/

        REQUEST JSON:
        {
            "id": "9"
        }

    
    Create Packages:
        POST /order/api/v1/package/create/

        REQUEST JSON:
        {
            "order_id" :"9",
            "packages": [
            {
                "description" : "Clothes",
                "dimensions" : "Big" ,
                "value" : "600",
                "fragile" : "False",
                "receiver_name" : "Akua mansa",
                "receiver_phone" : "0241223312"
            },
            {
                "description" : "Food",
                "dimensions" : "Small" ,
                "value" : "250",
                "fragile" : "True",
                "receiver_name" : "Mark Stone",
                "receiver_phone" : "0209988260"
            }
            ]
        }


    Update Package Receiver details:
        PUT /order/api/v1/package/update/

        REQUEST JSON:
        {
            "package_id": "PKGBC374761",
            "receiver_name" : "Akua mansa",
            "receiver_phone" : "020887765"
        }


    Create Deliveries for Packages:
        POST /delivery/api/v1/create/

        REQUEST JSON:
        {
            "deliveries": [
            {
                "package_id":"PKGBC374761",
                "address" : "Six to Six taxi station"

            },
            {
                "package_id":"PKGBE24072E",
                "address" : "nazareth methodist church mamprobi"
            }
        ]
        }


    Driver Delivery Update:
        PUT /delivery/api/v1/updatedelivery/

        REQUEST JSON:
        {
            "package_id": "PKGBC374761",
            "delivery_status": "picked_up"
        }