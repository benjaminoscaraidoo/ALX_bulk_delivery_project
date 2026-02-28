from rest_framework.throttling import SimpleRateThrottle

class OTPVerifyThrottle(SimpleRateThrottle):
    scope = "otp_verify"

    def get_cache_key(self, request, view):
        return self.get_ident(request)

class OTPRegisterThrottle(SimpleRateThrottle):
    scope = "otp_register"

    def get_cache_key(self, request, view):
        return self.get_ident(request)