from django.core.mail import send_mail
from django.conf import settings

def send_purchase_notification(email, order_id):
    subject = f'Order Confirmation #{order_id}'
    message = f'Thank you for your purchase! Your order #{order_id} is being processed.'
    from_email = settings.DEFAULT_FROM_EMAIL
    
    send_mail(
        subject,
        message,
        from_email,
        [email],
        fail_silently=True,
    )

def send_first_contact_notification(seller_email, buyer_name):
    subject = 'New Message from Buyer'
    message = f'Hello!\n\nYou have received a new message from a buyer: {buyer_name}.\n\nLog in to your dashboard to reply.'
    from_email = settings.DEFAULT_FROM_EMAIL
    
    send_mail(
        subject,
        message,
        from_email,
        [seller_email],
        fail_silently=True,
    )
