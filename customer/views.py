from django.shortcuts import render, redirect
from rest_framework import viewsets, permissions
from .models import CustomerProfile, DriverProfile
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views import View
from .forms import UpdateUserForm, ChangePasswordForm, CustomerProfileForm, DriverProfileForm
from django.http import JsonResponse
import jwt
from django.conf import settings
from django.contrib import messages
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (CustomerProfileSerializer,DriverProfileSerializer,MyTokenObtainPairSerializer)
from customer.models import CustomUser, CustomerProfile, DriverProfile

# Create your views here.

UserR = get_user_model()

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

class CustomerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomerProfile.objects.filter(user=self.request.user)


class DriverProfileViewSet(viewsets.ModelViewSet):
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DriverProfile.objects.filter(user=self.request.user)
    
#@login_required
def home(request):
    user = request.user

    if not user.is_authenticated:
        return render(request, 'home.html')
    
    
    if request.user.role == request.user.Role.CUSTOMER:
        return render(request, "customer/home.html")
    elif request.user.role == request.user.Role.DRIVER:
        return render(request, "driver/home.html")
    
@login_required
def driver_home(request):
    """Driver Home"""
    if request.user.role != request.user.Role.DRIVER:
        messages.error(request, "You are not authorized to view this page.")
        return redirect("customer:login")
    return render(request, "driver/home.html")



class Index(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/index.html')
    
class About(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/about.html')
    

def register_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        phone = request.POST.get("phone_number")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        role = request.POST.get("role", "customer")

        password = password2

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("customer:register")


        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("customer:register")

        user = CustomUser.objects.create_user(
            email=email,
            phone_number=phone,
            password=password2,
            role=role,
        )

        login(request, user)
        return redirect("customer:update_profile")

    return render(request, "auth/register.html")


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        print("Authenticated user:", user)
        if user is not None:
            login(request, user)
            request.session.set_expiry(settings.AUTO_LOGOUT.get('IDLE_TIME', 1800)) #session logout timer 10secs
            print("User logged in:", request.user)
            # Redirect based on role
            if user.role == user.Role.CUSTOMER:
                return redirect("customer:home")  # customer home
            elif user.role == user.Role.DRIVER:
                return redirect("customer:driver_home")  # driver home
            elif user.role == user.Role.ADMIN:
                return redirect("/admin/")  # admin dashboard

        else:
            messages.error(request, "Invalid login credentials")
            return redirect("customer:login")

    return render(request, "auth/login.html")



def session_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)  # 🔥 CREATES DJANGO SESSION
            request.session.set_expiry(settings.AUTO_LOGOUT.get('IDLE_TIME', 1800)) #session logout timer 10secs
            return JsonResponse({"success": True})
        return JsonResponse({"success": False}, status=401)
    


def logout_view(request):
    logout(request)
    return redirect("customer:login")


@login_required
def update_profileN(request):
    user = request.user

    # Determine profile based on role
    profile = None
    if user.role == user.Role.CUSTOMER:
        profile = getattr(user, "customer_profile", None)
        if not profile:
            profile = CustomerProfile.objects.create(user=user)
    elif user.role == user.Role.DRIVER:
        profile = getattr(user, "driverprofile", None)
        if not profile:
            profile = DriverProfile.objects.create(user=user)
    else:
        messages.info(request, "Admins do not have profiles to update.")
        return redirect("customer:home")

    if request.method == "POST":
        if user.role == user.Role.CUSTOMER:
            #profile.customer_name = request.POST.get("customer_name", profile.customer_name)
            profile.address = request.POST.get("address", profile.address)
        elif user.role == user.Role.DRIVER:
            profile.vehicle_type = request.POST.get("vehicle_type", profile.vehicle_type)
            profile.vehicle_number = request.POST.get("vehicle_number", profile.vehicle_number)
            profile.license_number = request.POST.get("license_number", profile.license_number)


        UserR.first_name = request.POST.get("firstName", UserR.first_name)
        UserR.last_name = request.POST.get("firstName", UserR.last_name)

        profile.save()
        messages.success(request, "Profile updated successfully!")

        UserR.save()
        messages.success(request, "User updated successfully!")
        return redirect("customer:home")

    return render(request, "customer/update_profile.html", {"profile": profile})



def update_profile(request):
    user = request.user
    
    # Identify the profile and the specific form class needed
    if user.role == user.Role.CUSTOMER:
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        ProfileFormClass = CustomerProfileForm
        role_label = "Customer"
    elif user.role == user.Role.DRIVER:
        profile, _ = DriverProfile.objects.get_or_create(user=user)
        ProfileFormClass = DriverProfileForm
        role_label = "Driver"
    else:
        messages.info(request, "Admins do not have profiles to update.")
        return redirect("customer:home")

    if request.method == "POST":
        user_form = UpdateUserForm(request.POST, instance=user)
        profile_form = ProfileFormClass(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("customer:home")
    else:
        user_form = UpdateUserForm(instance=user)
        profile_form = ProfileFormClass(instance=profile)

    return render(request, "customer/update_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
        "role_label": role_label
    })



def update_password(request):
	if request.user.is_authenticated:
		current_user = request.user
		# Did they fill out the form
		if request.method  == 'POST':
			form = ChangePasswordForm(current_user, request.POST)
			# Is the form valid
			if form.is_valid():
				form.save()
				messages.success(request, "Your Password Has Been Updated...")
				login(request, current_user)
				return redirect('update_user')
			else:
				for error in list(form.errors.values()):
					messages.error(request, error)
					return redirect('update_password')
		else:
			form = ChangePasswordForm(current_user)
			return render(request, "customer/update_password.html", {'form':form})
	else:
		messages.success(request, "You Must Be Logged In To View That Page...")
		return redirect('home')
     

def update_user(request):
	if request.user.is_authenticated:
		current_user = UserR.objects.get(id=request.user.id)
		user_form = UpdateUserForm(request.POST or None, instance=current_user)

		if user_form.is_valid():
			user_form.save()

			login(request, current_user)
			messages.success(request, "User Has Been Updated!!")
			return redirect('home')
		return render(request, "customer/update_user.html", {'user_form':user_form})
	else:
		messages.success(request, "You Must Be Logged In To Access That Page!!")
		return redirect('home')
    


def update_profile2(request):
    # Get the token from the Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return redirect("/customer/login1/")  # no token, redirect to login

    token = auth_header.split("Bearer ")[-1]

    try:
        # Decode JWT payload
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
        role = payload.get("role")
    except (jwt.ExpiredSignatureError, jwt.DecodeError, jwt.InvalidTokenError):
        messages.error(request, "Invalid or expired token. Please login again.")
        return redirect("/customer/login2/")

    # Fetch user from DB
    try:
        user = CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("/customer/login/")

    # Determine profile based on role
    profile = None
    if role == CustomUser.Role.CUSTOMER:
        profile = getattr(user, "customer_profile", None)
        if not profile:
            profile = CustomerProfile.objects.create(user=user)
    elif role == CustomUser.Role.DRIVER:
        profile = getattr(user, "driverprofile", None)
        if not profile:
            profile = DriverProfile.objects.create(user=user)
    else:
        messages.info(request, "Admins do not have profiles to update.")
        return redirect("/customer/home/")

    # Handle form submission
    if request.method == "POST":
        if role == CustomUser.Role.CUSTOMER:
            profile.customer_name = request.POST.get("customer_name", profile.customer_name)
            profile.address = request.POST.get("address", profile.address)
        elif role == CustomUser.Role.DRIVER:
            profile.vehicle_type = request.POST.get("vehicle_type", profile.vehicle_type)
            profile.vehicle_number = request.POST.get("vehicle_number", profile.vehicle_number)
            profile.license_number = request.POST.get("license_number", profile.license_number)
            profile.phone = request.POST.get("phone", profile.phone)

        profile.save()
        messages.success(request, "Profile updated successfully!")
        return redirect("/home/")  # or role-based home

    return render(request, "customer/update_profile.html", {"profile": profile, "role": role})