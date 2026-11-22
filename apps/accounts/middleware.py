from django.shortcuts import redirect
from django.urls import reverse

from apps.electricians.models import ElectricianProfile


class ElectricianApprovalMiddleware:
    allowed_url_names = {
        "accounts:electrician_access",
        "accounts:submit_payment",
        "accounts:logout",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.is_electrician and not user.is_administrator:
            access_status = ElectricianProfile.objects.filter(
                user=user
            ).values_list("access_status", flat=True).first()
            if access_status != ElectricianProfile.AccessStatus.ACTIVE:
                allowed_paths = {
                    reverse(url_name) for url_name in self.allowed_url_names
                }
                allowed_paths.add(reverse(
                    "accounts:payment_receipt",
                    args=[user.pk],
                ))
                if request.path_info not in allowed_paths:
                    return redirect(reverse("accounts:electrician_access"))
        return self.get_response(request)
