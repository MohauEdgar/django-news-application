"""
Management command: python manage.py setup_groups

Creates the three role groups (Reader, Journalist, Editor) and assigns
the appropriate model-level permissions to each.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from news.models import Article, Newsletter


class Command(BaseCommand):
    help = 'Create role groups (Reader, Journalist, Editor) with correct permissions.'

    def handle(self, *args, **options):
        article_ct = ContentType.objects.get_for_model(Article)
        newsletter_ct = ContentType.objects.get_for_model(Newsletter)

        # Permissions for Article
        view_article = Permission.objects.get(codename='view_article', content_type=article_ct)
        add_article = Permission.objects.get(codename='add_article', content_type=article_ct)
        change_article = Permission.objects.get(codename='change_article', content_type=article_ct)
        delete_article = Permission.objects.get(codename='delete_article', content_type=article_ct)

        # Permissions for Newsletter
        view_newsletter = Permission.objects.get(codename='view_newsletter', content_type=newsletter_ct)
        add_newsletter = Permission.objects.get(codename='add_newsletter', content_type=newsletter_ct)
        change_newsletter = Permission.objects.get(codename='change_newsletter', content_type=newsletter_ct)
        delete_newsletter = Permission.objects.get(codename='delete_newsletter', content_type=newsletter_ct)

        # --- Reader group ---
        reader_group, created = Group.objects.get_or_create(name='Reader')
        reader_group.permissions.set([view_article, view_newsletter])
        self.stdout.write(self.style.SUCCESS(f'Reader group {"created" if created else "updated"}.'))

        # --- Editor group ---
        editor_group, created = Group.objects.get_or_create(name='Editor')
        editor_group.permissions.set([
            view_article, change_article, delete_article,
            view_newsletter, change_newsletter, delete_newsletter,
        ])
        self.stdout.write(self.style.SUCCESS(f'Editor group {"created" if created else "updated"}.'))

        # --- Journalist group ---
        journalist_group, created = Group.objects.get_or_create(name='Journalist')
        journalist_group.permissions.set([
            view_article, add_article, change_article, delete_article,
            view_newsletter, add_newsletter, change_newsletter, delete_newsletter,
        ])
        self.stdout.write(self.style.SUCCESS(f'Journalist group {"created" if created else "updated"}.'))

        self.stdout.write(self.style.SUCCESS('All role groups configured successfully.'))
