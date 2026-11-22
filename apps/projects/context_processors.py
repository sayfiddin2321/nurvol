from .models import Project


def project_navigation(request):
    user = request.user
    sidebar_project = None
    unread_inquiry_count = 0
    pending_electrician_count = 0

    if user.is_authenticated:
        if user.is_administrator:
            projects = Project.objects.all()
            from apps.electricians.models import ElectricianProfile
            pending_electrician_count = ElectricianProfile.objects.filter(
                user__role="electrician",
                access_status__in=[
                    ElectricianProfile.AccessStatus.PENDING_PAYMENT,
                    ElectricianProfile.AccessStatus.PAYMENT_SUBMITTED,
                ],
            ).count()
        elif user.is_electrician:
            projects = Project.objects.filter(electrician=user)
        else:
            projects = Project.objects.filter(client=user)
        if user.can_use_electrician_tools:
            from apps.electricians.models import ElectricianInquiry
            unread_inquiry_count = ElectricianInquiry.objects.filter(
                electrician=user,
                is_read=False,
            ).count()
        sidebar_project = projects.only("pk", "name").first()

    return {
        "sidebar_project": sidebar_project,
        "unread_inquiry_count": unread_inquiry_count,
        "pending_electrician_count": pending_electrician_count,
    }
