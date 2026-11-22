from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = "admin"
        return super().create_superuser(username, email, password, **extra_fields)

    create_superuser.alters_data = True

    async def acreate_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields["role"] = "admin"
        return await super().acreate_superuser(username, email, password, **extra_fields)

    acreate_superuser.alters_data = True
