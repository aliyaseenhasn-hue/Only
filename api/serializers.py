from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class UserProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'user',
            'display_name',
            'instagram_handle',
            'avatar_url',
            'bio',
            'latitude',
            'longitude',
            'is_online',
            'last_seen',
        ]


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    display_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    instagram_handle = serializers.CharField(max_length=100, required=False, allow_blank=True)
    avatar_url = serializers.URLField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already taken')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        profile = UserProfile.objects.create(
            user=user,
            display_name=validated_data.get('display_name', validated_data['username']),
            instagram_handle=validated_data.get('instagram_handle', ''),
            avatar_url=validated_data.get('avatar_url', ''),
            bio=validated_data.get('bio', ''),
        )
        return profile


class NearbyPersonSerializer(serializers.Serializer):
    display_name = serializers.CharField()
    email = serializers.EmailField()
    instagram_handle = serializers.CharField()
    avatar_url = serializers.URLField()
    distance = serializers.FloatField()
    direction = serializers.CharField()
    is_online = serializers.BooleanField()
