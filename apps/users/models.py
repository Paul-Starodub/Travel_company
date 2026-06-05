from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    pass

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.username
