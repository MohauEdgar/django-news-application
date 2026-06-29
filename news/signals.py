"""
Django Signals — Option 1 implementation.

Listens for Article post_save events; when an article transitions to approved,
it emails subscribers and posts to X (Twitter).
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Article
from .services import notify_subscribers, post_to_x

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Article)
def on_article_saved(sender, instance, created, **kwargs):
    """
    Triggered after every Article save.
    Only acts when the article has just been approved (approved=True).
    Uses update_fields awareness to avoid double-firing on unrelated saves.
    """
    update_fields = kwargs.get('update_fields')

    # If update_fields is provided, only proceed if 'approved' is being set
    if update_fields is not None and 'approved' not in update_fields:
        return

    if instance.approved:
        logger.info('Article "%s" approved — notifying subscribers and posting to X.', instance.title)
        notify_subscribers(instance)
        post_to_x(instance)
