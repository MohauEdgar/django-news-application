"""Serializers for the News Application REST API."""

from rest_framework import serializers
from .models import CustomUser, Publisher, Article, Newsletter


class PublisherSerializer(serializers.ModelSerializer):
    """Serialize Publisher instances to/from JSON."""
    class Meta:
        model = Publisher
        fields = ['id', 'name', 'description', 'website', 'created_at']
        read_only_fields = ['created_at']


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user profiles — hides sensitive fields."""
    subscribed_publishers = PublisherSerializer(many=True, read_only=True)
    # Only expose the IDs for journalist subscriptions (avoid deep nesting)
    subscribed_journalists = serializers.PrimaryKeyRelatedField(
        many=True,
        read_only=True,
    )

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'bio', 'publisher',
            'subscribed_publishers', 'subscribed_journalists',
        ]
        read_only_fields = ['role']


class ArticleSerializer(serializers.ModelSerializer):
    """Serialize Article instances; exposes author username and publisher name as read-only."""
    author_username = serializers.CharField(source='author.username', read_only=True)
    publisher_name = serializers.CharField(source='publisher.name', read_only=True, allow_null=True)

    class Meta:
        model = Article
        fields = [
            'id', 'title', 'content', 'author', 'author_username',
            'created_at', 'updated_at', 'approved', 'approved_by', 'approved_at',
            'publisher', 'publisher_name',
        ]
        read_only_fields = ['author', 'created_at', 'updated_at', 'approved', 'approved_by', 'approved_at']

    def create(self, validated_data):
        # Automatically assign the authenticated user as the author
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class ArticleApprovalSerializer(serializers.ModelSerializer):
    """Minimal serializer used by the editor approval endpoint."""
    class Meta:
        model = Article
        fields = ['approved']


class NewsletterSerializer(serializers.ModelSerializer):
    """Serialize Newsletter instances; accepts article_ids on write and returns full articles on read."""
    author_username = serializers.CharField(source='author.username', read_only=True)
    articles = ArticleSerializer(many=True, read_only=True)
    article_ids = serializers.PrimaryKeyRelatedField(
        queryset=Article.objects.all(),
        many=True,
        write_only=True,
        source='articles',
    )

    class Meta:
        model = Newsletter
        fields = [
            'id', 'title', 'description', 'created_at', 'updated_at',
            'author', 'author_username', 'articles', 'article_ids',
        ]
        read_only_fields = ['author', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class RegisterSerializer(serializers.ModelSerializer):
    """Handles new user registration."""
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, label='Confirm password')

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'password2', 'role', 'first_name', 'last_name']

    def validate(self, data):
        """Ensure both password fields match before saving."""
        if data['password'] != data['password2']:
            raise serializers.ValidationError({'password2': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        """Hash the password and create the user record."""
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)
        user.save()
        return user
