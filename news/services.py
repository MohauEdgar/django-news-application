"""
Business-logic services for article approval side-effects:
  - Email subscribers of the article's author/publisher.
  - Post a tweet to the configured X (Twitter) account.
"""

import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_subscribers(article):
    """
    Send an approval notification email to every subscriber of the article's
    author (journalist) and the article's publisher (if any).
    """
    subscriber_emails = set()

    # Collect readers subscribed to this journalist
    for reader in article.author.journalist_subscribers.all():
        if reader.email:
            subscriber_emails.add(reader.email)

    # Collect readers subscribed to the publisher (if applicable)
    if article.publisher:
        for reader in article.publisher.subscribers.all():
            if reader.email:
                subscriber_emails.add(reader.email)

    if not subscriber_emails:
        logger.info('No subscribers to notify for article "%s".', article.title)
        return

    subject = f'New Article: {article.title}'
    message = (
        f'A new article has been published:\n\n'
        f'Title: {article.title}\n'
        f'Author: {article.author.get_full_name() or article.author.username}\n'
        f'{f"Publisher: {article.publisher.name}" if article.publisher else "Independent article"}\n\n'
        f'{article.content[:500]}...\n\n'
        f'Log in to read the full article.'
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(subscriber_emails),
            fail_silently=False,
        )
        logger.info(
            'Notified %d subscriber(s) about article "%s".',
            len(subscriber_emails),
            article.title,
        )
    except Exception as exc:
        logger.error('Failed to send subscriber emails for article "%s": %s', article.title, exc)


def post_to_x(article):
    """
    Post a tweet announcing the newly approved article to the configured X account.
    Uses the X API v2 /tweets endpoint with OAuth 1.0a User Context.
    """
    bearer_token = settings.X_BEARER_TOKEN
    api_key = settings.X_API_KEY
    api_secret = settings.X_API_SECRET
    access_token = settings.X_ACCESS_TOKEN
    access_token_secret = settings.X_ACCESS_TOKEN_SECRET

    # Skip posting if credentials are not configured
    if not all([api_key, api_secret, access_token, access_token_secret]):
        logger.warning('X API credentials not configured; skipping tweet for "%s".', article.title)
        return

    tweet_text = (
        f'New article published: "{article.title}" '
        f'by {article.author.get_full_name() or article.author.username}.'
    )
    # Truncate to X's 280-character limit
    tweet_text = tweet_text[:280]

    try:
        from requests_oauthlib import OAuth1
        auth = OAuth1(api_key, api_secret, access_token, access_token_secret)
        response = requests.post(
            'https://api.twitter.com/2/tweets',
            json={'text': tweet_text},
            auth=auth,
            timeout=10,
        )
        response.raise_for_status()
        logger.info('Tweet posted for article "%s": %s', article.title, response.json())
    except ImportError:
        # requests_oauthlib not installed; fall back to bearer-token-only approach
        logger.warning(
            'requests_oauthlib not installed; cannot post OAuth tweet. '
            'Install it with: pip install requests-oauthlib'
        )
    except requests.RequestException as exc:
        logger.error('Failed to post tweet for article "%s": %s', article.title, exc)
