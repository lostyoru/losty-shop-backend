from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db import IntegrityError

from core.permissions import IsAdmin, IsSeller, IsUser
from core.utils.cloudinary import upload_image, delete_image
from .models import Category, Product, Review
from .serializers import (
    CategorySerializer, ProductSerializer, CreateProductSerializer,
    ReviewSerializer, CreateReviewSerializer
)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return []  # AllowAny for list/retrieve


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'seller']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'seller_products']:
            return [IsSeller()]
        return []

    def create(self, request, *args, **kwargs):
        serializer = CreateProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        images = request.FILES.getlist('images')
        image_urls = []
        for img in images:
            res = upload_image(img, folder='products')
            image_urls.append(res['secure_url'])
            
        product = serializer.save(seller=request.auth_entity, images=image_urls)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        product = self.get_object()
        if product.seller != request.auth_entity:
            return Response(status=status.HTTP_403_FORBIDDEN)
            
        serializer = CreateProductSerializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        current_images = list(product.images or [])

        # request.data.getlist('images') can contain kept URL strings in multipart payload.
        raw_images = request.data.getlist('images') if hasattr(request.data, 'getlist') else []
        kept_images_raw = request.data.getlist('keptImages') if hasattr(request.data, 'getlist') else []
        kept_urls = [img for img in kept_images_raw if isinstance(img, str) and img.strip()]
        if not kept_urls:
            kept_urls = [img for img in raw_images if isinstance(img, str) and img.strip()]

        # New uploaded files for replacement/addition.
        uploaded_files = request.FILES.getlist('images')
        uploaded_urls = []
        for img in uploaded_files:
            res = upload_image(img, folder='products')
            uploaded_urls.append(res['secure_url'])

        should_update_images = bool(raw_images) or bool(uploaded_files) or bool(request.data.get('mainImage'))
        if should_update_images:
            # If UI sends no kept URLs but only mainImage and no files, keep current set.
            final_images = (kept_urls if kept_urls else current_images.copy()) + uploaded_urls

            # Keep order unique and stable.
            seen = set()
            deduped_images = []
            for url in final_images:
                if url and url not in seen:
                    deduped_images.append(url)
                    seen.add(url)

            main_image = request.data.get('mainImage')
            if main_image and main_image in deduped_images:
                deduped_images = [main_image] + [u for u in deduped_images if u != main_image]

            serializer.validated_data['images'] = deduped_images

            # Delete only removed images from Cloudinary.
            removed_images = [url for url in current_images if url not in deduped_images]
            for url in removed_images:
                delete_image(url)
            
        product = serializer.save()
        return Response(ProductSerializer(product).data)

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        if product.seller != request.auth_entity:
            return Response(status=status.HTTP_403_FORBIDDEN)
        for url in product.images:
            delete_image(url)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def seller_products(self, request):
        products = Product.objects.filter(seller=request.auth_entity)
        return Response(ProductSerializer(products, many=True).data)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer

    def get_queryset(self):
        product_id = self.kwargs.get('product_pk')
        if product_id:
            return Review.objects.filter(product_id=product_id)
        return Review.objects.all()

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsUser()]
        return []

    def create(self, request, *args, **kwargs):
        product_id = self.kwargs.get('product_pk')
        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            review = serializer.save(user=request.auth_entity, product_id=product_id)
            return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response({'detail': 'You have already reviewed this product'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_update(self, serializer):
        if self.get_object().user != self.request.auth_entity:
            raise PermissionError
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.auth_entity:
            raise PermissionError
        instance.delete()
