import uuid
from django.db import models
from django.utils import timezone
from accounts.models import User, Seller

class ChatMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    sender_id = models.UUIDField()
    sender_type = models.CharField(max_length=50) # 'user' or 'seller'
    
    receiver_id = models.UUIDField()
    receiver_type = models.CharField(max_length=50) # 'user' or 'seller'
    
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chat_messages'
        ordering = ['created_at']

    # Helper properties
    @property
    def sender_is_user(self):
        return self.sender_type == 'user'

    @property
    def receiver_is_user(self):
        return self.receiver_type == 'user'


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    recipient_id = models.UUIDField()
    recipient_type = models.CharField(max_length=20) # 'user' or 'seller'
    
    type = models.CharField(max_length=50)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    
    metadata = models.JSONField(null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
