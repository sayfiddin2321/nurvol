from .models import Project


def user_can_access_project(user, project):
    if not user.is_authenticated:
        return project.is_public
    if user.is_administrator:
        return True
    return project.electrician_id == user.id or project.client_id == user.id


def user_can_view_project_media(user, project):
    """Public files remain public for signed-in visitors from other accounts."""
    return project.is_public or user_can_access_project(user, project)

def user_can_edit_project(user, project):
    if not user.is_authenticated:
        return False
    return project.electrician_id == user.id or user.is_administrator


def create_revision(project, user, title, description=""):
    from apps.documents.models import ProjectRevision

    last_revision = project.revisions.order_by("-revision_number").first()
    revision_number = last_revision.revision_number + 1 if last_revision else 1
    return ProjectRevision.objects.create(
        project=project,
        changed_by=user,
        title=title,
        description=description,
        revision_number=revision_number,
    )
