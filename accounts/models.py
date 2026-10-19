
from django.db import models


class PendingSignup(models.Model):
    username = models.CharField(max_length=150)
    email = models.EmailField(db_index=True)
    password_hash = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} <{self.email}>"
