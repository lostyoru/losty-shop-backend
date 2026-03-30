from rest_framework import serializers
from .models import ChatMessage, Notification

class ChatMessageSerializer(serializers.ModelSerializer):
    senderId = serializers.UUIDField(source='sender_id')
    senderType = serializers.CharField(source='sender_type')
    receiverId = serializers.UUIDField(source='receiver_id')
    receiverType = serializers.CharField(source='receiver_type')
    isRead = serializers.BooleanField(source='is_read', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'senderId', 'senderType', 'receiverId', 'receiverType', 'content', 'isRead', 'createdAt', 'updatedAt']


class SendMessageSerializer(serializers.Serializer):
    receiverId = serializers.UUIDField()
    receiverType = serializers.CharField()
    content = serializers.CharField()


class NotificationSerializer(serializers.ModelSerializer):
    recipientId = serializers.UUIDField(source='recipient_id')
    recipientType = serializers.CharField(source='recipient_type')
    isRead = serializers.BooleanField(source='is_read', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'recipientId', 'recipientType', 'type', 'title', 'message', 'isRead', 'metadata', 'createdAt', 'updatedAt']
