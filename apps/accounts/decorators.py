from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def head_electrician_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_administrator:
            return HttpResponseForbidden("Bu bo'lim faqat bosh elektrik uchun.")
        return view(request, *args, **kwargs)

    return wrapped
