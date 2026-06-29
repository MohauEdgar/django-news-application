from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Publisher, Article, Newsletter


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'publisher', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('News App', {'fields': ('role', 'bio', 'publisher',
                                 'subscribed_publishers', 'subscribed_journalists')}),
    )
    filter_horizontal = ('subscribed_publishers', 'subscribed_journalists',
                         'groups', 'user_permissions')


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ('name', 'website', 'created_at')
    search_fields = ('name',)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'publisher', 'approved', 'created_at')
    list_filter = ('approved', 'publisher')
    search_fields = ('title', 'author__username')
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    actions = ['approve_articles']

    @admin.action(description='Approve selected articles')
    def approve_articles(self, request, queryset):
        from django.utils import timezone
        queryset.update(approved=True, approved_by=request.user, approved_at=timezone.now())


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'created_at')
    search_fields = ('title', 'author__username')
    filter_horizontal = ('articles',)
