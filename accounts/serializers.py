from rest_framework import serializers
from .models import User, Seller, Admin

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'role', 
            'profile_picture', 'is_active', 'two_factor_enabled', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'role', 'is_active', 'created_at', 'updated_at']

class CreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'username']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class SellerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = [
            'id', 'email', 'full_name', 'store_name', 'store_description', 
            'profile_picture', 'role', 'two_factor_enabled', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'role', 'created_at', 'updated_at']

class CreateSellerSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Seller
        fields = ['email', 'password', 'full_name', 'store_name']

class SellerPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = ['id', 'store_name', 'store_description', 'profile_picture', 'created_at']


class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = ['id', 'username', 'email', 'role', 'created_at']
        read_only_fields = ['id', 'role', 'created_at']

class CreateAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Admin
        fields = ['username', 'email', 'password']
        
        
class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
