from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models


class Publisher(models.Model):
    """A publication that employs editors and journalists."""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    """
    Custom user model supporting Reader, Journalist, and Editor roles.
    Role-specific fields are populated based on the assigned role; others are None.
    """

    class Role(models.TextChoices):
        READER = 'reader', 'Reader'
        JOURNALIST = 'journalist', 'Journalist'
        EDITOR = 'editor', 'Editor'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READER,
    )
    bio = models.TextField(blank=True)

    # Reader-only: subscriptions to publishers and journalists
    subscribed_publishers = models.ManyToManyField(
        Publisher,
        blank=True,
        related_name='subscribers',
        help_text='Publishers this reader has subscribed to.',
    )
    subscribed_journalists = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='journalist_subscribers',
        help_text='Journalists this reader follows.',
    )

    # Journalist/Editor-only: employer publisher (optional for independent journalists)
    publisher = models.ForeignKey(
        Publisher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='staff',
    )

    # Override groups/permissions to avoid reverse accessor clashes
    groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='custom_users',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='custom_users',
    )

    def save(self, *args, **kwargs):
        # Readers are not publisher staff members
        if self.role == self.Role.READER:
            self.publisher = None
        super().save(*args, **kwargs)
        self._assign_role_group()

    def _assign_role_group(self):
        """Place user in the group that matches their role (and only that role group)."""
        role_group_map = {
            self.Role.READER: 'Reader',
            self.Role.JOURNALIST: 'Journalist',
            self.Role.EDITOR: 'Editor',
        }
        target_name = role_group_map.get(self.role)
        if not target_name:
            return
        target_group, _ = Group.objects.get_or_create(name=target_name)
        # Remove all role groups, then add the correct one
        all_role_groups = Group.objects.filter(name__in=role_group_map.values())
        self.groups.remove(*all_role_groups)
        self.groups.add(target_group)

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'


class Article(models.Model):
    """A news article written by a journalist or editor."""
    title = models.CharField(max_length=300)
    content = models.TextField()
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='authored_articles',
        limit_choices_to={'role__in': [CustomUser.Role.JOURNALIST, CustomUser.Role.EDITOR]},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Approval workflow
    approved = models.BooleanField(
        default=False,
        help_text='Set to True by an Editor to publish the article.',
    )
    approved_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_articles',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Optional association with a publisher (None means independent article)
    publisher = models.ForeignKey(
        Publisher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='articles',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'approved' if self.approved else 'pending'
        return f'{self.title} by {self.author.username} [{status}]'


class Newsletter(models.Model):
    """A curated collection of articles assembled by a journalist or editor."""
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='newsletters',
        limit_choices_to={'role__in': [CustomUser.Role.JOURNALIST, CustomUser.Role.EDITOR]},
    )
    articles = models.ManyToManyField(
        Article,
        blank=True,
        related_name='newsletters',
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} by {self.author.username}'
