import json
import jwt
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        token = self.scope.get('auth_token')
        if not token:
            query_string = self.scope.get('query_string', b'').decode()
            params = dict(p.split('=') for p in query_string.split('&') if '=' in p)
            token = params.get('token')

        if not token:
            await self.close()
            return

        try:
            payload = jwt.decode(
                token,
                settings.SIMPLE_JWT.get('SIGNING_KEY', settings.SECRET_KEY),
                algorithms=['HS256']
            )
            self.user_id = payload.get('sub')
            self.user_type = payload.get('userType', 'user')
        except jwt.InvalidTokenError:
            await self.close()
            return

        await self.channel_layer.group_add(f'user_{self.user_id}', self.channel_name)
        await self.channel_layer.group_add(f'type_{self.user_type}', self.channel_name)
        await self.accept()

        from communications.models import Notification
        from asgiref.sync import sync_to_async
        count = await sync_to_async(Notification.objects.filter(recipient_id=self.user_id, is_read=False).count)()
        await self.send(json.dumps({'type': 'unreadCount', 'count': count}))

    async def disconnect(self, close_code):
        if hasattr(self, 'user_id'):
            await self.channel_layer.group_discard(f'user_{self.user_id}', self.channel_name)
            await self.channel_layer.group_discard(f'type_{self.user_type}', self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'markAsRead':
            from communications.models import Notification
            from asgiref.sync import sync_to_async
            notification_ids = data.get('notificationIds', [])
            await sync_to_async(Notification.objects.filter(id__in=notification_ids, recipient_id=self.user_id).update)(is_read=True)
            count = await sync_to_async(Notification.objects.filter(recipient_id=self.user_id, is_read=False).count)()
            await self.send(json.dumps({'type': 'unreadCount', 'count': count}))

    async def send_notification(self, event):
        await self.send(json.dumps({'type': 'notification', **event['notification']}))
