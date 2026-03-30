import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsUserOrSeller
from core.utils.mail import send_first_contact_notification
from accounts.models import Seller, User
from .models import ChatMessage, Notification
from .serializers import ChatMessageSerializer, SendMessageSerializer, NotificationSerializer


class ChatViewSet(viewsets.ViewSet):
    permission_classes = [IsUserOrSeller]

    @action(detail=False, methods=['post'])
    def send(self, request):
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        sender_id = request.auth_entity.id
        sender_type = request.auth_user_type

        # Serializer accepts camelCase keys; keep snake_case fallback for compatibility.
        receiver_id = serializer.validated_data.get('receiverId') or serializer.validated_data.get('receiver_id')
        receiver_type = serializer.validated_data.get('receiverType') or serializer.validated_data.get('receiver_type')
        
        # Check if first message to send email
        is_first_message = not ChatMessage.objects.filter(
            Q(sender_id=sender_id, receiver_id=receiver_id) |
            Q(sender_id=receiver_id, receiver_id=sender_id)
        ).exists()

        message = ChatMessage.objects.create(
            sender_id=sender_id,
            sender_type=sender_type,
            receiver_id=receiver_id,
            receiver_type=receiver_type,
            content=serializer.validated_data['content']
        )
        
        if is_first_message and receiver_type == 'seller':
            buyer_name = getattr(request.auth_entity, 'full_name', 'A buyer')
            try:
                seller = Seller.objects.get(id=receiver_id)
                send_first_contact_notification(seller.email, buyer_name)
            except Seller.DoesNotExist:
                pass
            
        # Socket notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{receiver_id}',
            {
                'type': 'send_notification',
                'notification': {
                    'type': 'NEW_MESSAGE',
                    'message': ChatMessageSerializer(message).data
                }
            }
        )

        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def conversations(self, request):
        user_id = str(request.auth_entity.id)
        messages = ChatMessage.objects.filter(
            Q(sender_id=user_id) | Q(receiver_id=user_id)
        ).order_by('-created_at')
        
        conversations = {}
        for msg in messages:
            partner_id = str(msg.receiver_id) if str(msg.sender_id) == user_id else str(msg.sender_id)
            partner_type = msg.receiver_type if str(msg.sender_id) == user_id else msg.sender_type
            
            if partner_id not in conversations:
                conversations[partner_id] = {
                    'partnerId': partner_id,
                    'partnerType': partner_type,
                    'lastMessage': msg.content,
                    'timestamp': msg.created_at,
                    'unreadCount': 0
                }
            if not msg.is_read and str(msg.receiver_id) == user_id:
                conversations[partner_id]['unreadCount'] += 1
                
        # Fetch partner details
        for partner_id, conv in conversations.items():
            if conv['partnerType'] == 'user':
                user = User.objects.filter(id=partner_id).first()
                if user:
                    conv['partner'] = {
                        'id': str(user.id),
                        'name': user.full_name,
                        'avatar': user.profile_picture
                    }
            else:
                seller = Seller.objects.filter(id=partner_id).first()
                if seller:
                    conv['partner'] = {
                        'id': str(seller.id),
                        'name': seller.store_name,
                        'avatar': seller.profile_picture
                    }
                
        return Response(list(conversations.values()))

    @action(detail=False, methods=['get'], url_path=r'conversation/(?P<partner_id>[^/.]+)')
    def conversation(self, request, partner_id=None):
        user_id = str(request.auth_entity.id)
        messages = ChatMessage.objects.filter(
            Q(sender_id=user_id, receiver_id=partner_id) |
            Q(sender_id=partner_id, receiver_id=user_id)
        ).order_by('created_at')
        return Response(ChatMessageSerializer(messages, many=True).data)

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        message_ids = request.data.get('messageIds', [])
        ChatMessage.objects.filter(
            id__in=message_ids, 
            receiver_id=request.auth_entity.id
        ).update(is_read=True)
        return Response({'success': True})


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient_id=self.request.auth_entity.id)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'notifications': serializer.data,
                'total': queryset.count()
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'notifications': serializer.data,
            'total': queryset.count()
        })

    @action(detail=False, methods=['post'], url_path='mark-read')
    def mark_read(self, request):
        ids = request.data.get('notificationIds', [])
        Notification.objects.filter(id__in=ids, recipient_id=request.auth_entity.id).update(is_read=True)
        return Response({'success': True})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        Notification.objects.filter(recipient_id=request.auth_entity.id).update(is_read=True)
        return Response({'success': True})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(recipient_id=request.auth_entity.id, is_read=False).count()
        return Response({'count': count})
