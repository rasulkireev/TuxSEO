import uuid

from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        """Soft delete the instance by setting deleted_at to the current timestamp."""
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
