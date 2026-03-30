import cloudinary.uploader
import cloudinary.api
from django.conf import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CONFIG['cloud_name'],
    api_key=settings.CLOUDINARY_CONFIG['api_key'],
    api_secret=settings.CLOUDINARY_CONFIG['api_secret']
)

def upload_image(file_obj, folder='products'):
    result = cloudinary.uploader.upload(
        file_obj,
        folder=folder,
        resource_type="auto"
    )
    return result

def upload_profile_picture(file_obj):
    result = cloudinary.uploader.upload(
        file_obj,
        folder='profiles',
        transformation=[
            {'width': 500, 'height': 500, 'crop': "fill", 'gravity': "face"},
            {'quality': "auto", 'fetch_format': "auto"}
        ]
    )
    return result

def extract_public_id(url):
    parts = url.split('/')
    try:
        upload_index = parts.index('upload')
        if len(parts) > upload_index + 2:
            return '/'.join(parts[upload_index + 2:]).split('.')[0]
    except ValueError:
        pass
    return None

def delete_image(url):
    public_id = extract_public_id(url)
    if public_id:
        return cloudinary.uploader.destroy(public_id)
    return None
