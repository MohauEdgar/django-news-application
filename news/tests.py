"""
Automated unit tests for the News Application RESTful API.

Coverage:
  - Authenticated access per role (Reader, Journalist, Editor)
  - Reader can only retrieve approved / subscribed content
  - Journalist can create articles
  - Editor can approve and delete
  - Newsletter CRUD behaviour
  - Signal / service logic (email + X) using mocking
  - Both successful and failed request scenarios
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, Publisher, Article, Newsletter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, role, publisher=None, password='TestPass123!'):
    """Create and return a user with the given role."""
    user = CustomUser.objects.create_user(
        username=username,
        password=password,
        email=f'{username}@example.com',
        role=role,
        publisher=publisher,
    )
    return user


def auth_client(user):
    """Return an APIClient authenticated via JWT for the given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class CustomUserModelTest(TestCase):
    def test_reader_has_no_publisher(self):
        pub = Publisher.objects.create(name='Daily News')
        reader = make_user('reader1', CustomUser.Role.READER, publisher=pub)
        self.assertIsNone(reader.publisher)

    def test_journalist_keeps_publisher(self):
        pub = Publisher.objects.create(name='Tech Weekly')
        journalist = make_user('journo1', CustomUser.Role.JOURNALIST, publisher=pub)
        self.assertEqual(journalist.publisher, pub)

    def test_user_assigned_to_correct_group(self):
        reader = make_user('reader2', CustomUser.Role.READER)
        journalist = make_user('journo2', CustomUser.Role.JOURNALIST)
        editor = make_user('editor1', CustomUser.Role.EDITOR)
        self.assertTrue(reader.groups.filter(name='Reader').exists())
        self.assertTrue(journalist.groups.filter(name='Journalist').exists())
        self.assertTrue(editor.groups.filter(name='Editor').exists())

    def test_reader_not_in_journalist_group(self):
        reader = make_user('reader3', CustomUser.Role.READER)
        self.assertFalse(reader.groups.filter(name='Journalist').exists())


# ---------------------------------------------------------------------------
# Article API tests
# ---------------------------------------------------------------------------

class ArticleListAPITest(APITestCase):
    def setUp(self):
        self.publisher = Publisher.objects.create(name='The Gazette')
        self.journalist = make_user('journo', CustomUser.Role.JOURNALIST, self.publisher)
        self.reader = make_user('reader', CustomUser.Role.READER)
        self.editor = make_user('editor', CustomUser.Role.EDITOR)
        self.approved_article = Article.objects.create(
            title='Approved Article',
            content='Content here.',
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
            approved_by=self.editor,
            approved_at=timezone.now(),
        )
        self.pending_article = Article.objects.create(
            title='Pending Article',
            content='Not approved yet.',
            author=self.journalist,
        )

    def test_unauthenticated_cannot_list_articles(self):
        response = self.client.get(reverse('api_article_list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reader_sees_only_approved_articles(self):
        client = auth_client(self.reader)
        response = client.get(reverse('api_article_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Approved Article', titles)
        self.assertNotIn('Pending Article', titles)

    def test_api_article_list_only_returns_approved(self):
        """The public article list endpoint only exposes approved articles."""
        client = auth_client(self.journalist)
        response = client.get(reverse('api_article_list'))
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Approved Article', titles)
        self.assertNotIn('Pending Article', titles)


class ArticleCreateAPITest(APITestCase):
    def setUp(self):
        self.publisher = Publisher.objects.create(name='Science Today')
        self.journalist = make_user('journo_create', CustomUser.Role.JOURNALIST, self.publisher)
        self.reader = make_user('reader_create', CustomUser.Role.READER)
        self.editor = make_user('editor_create', CustomUser.Role.EDITOR)

    def test_journalist_can_create_article(self):
        client = auth_client(self.journalist)
        data = {'title': 'New Discovery', 'content': 'Scientists found...', 'publisher': self.publisher.pk}
        response = client.post(reverse('api_article_list'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Discovery')
        self.assertFalse(response.data['approved'])

    def test_reader_cannot_create_article(self):
        client = auth_client(self.reader)
        data = {'title': 'Fake News', 'content': 'Some content.'}
        response = client.post(reverse('api_article_list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_cannot_post_via_journalist_endpoint(self):
        """POST /api/articles/ is restricted to journalists only."""
        client = auth_client(self.editor)
        data = {'title': 'Editor Article', 'content': 'Some content.'}
        response = client.post(reverse('api_article_list'), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ArticleApprovalAPITest(APITestCase):
    def setUp(self):
        self.journalist = make_user('journo_appr', CustomUser.Role.JOURNALIST)
        self.editor = make_user('editor_appr', CustomUser.Role.EDITOR)
        self.reader = make_user('reader_appr', CustomUser.Role.READER)
        self.article = Article.objects.create(
            title='To Be Approved',
            content='Content.',
            author=self.journalist,
        )

    def test_editor_can_approve_article(self):
        client = auth_client(self.editor)
        url = reverse('api_article_approve', kwargs={'pk': self.article.pk})
        with patch('news.signals.notify_subscribers'), patch('news.signals.post_to_x'):
            response = client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.article.refresh_from_db()
        self.assertTrue(self.article.approved)

    def test_reader_cannot_approve_article(self):
        client = auth_client(self.reader)
        url = reverse('api_article_approve', kwargs={'pk': self.article.pk})
        response = client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_journalist_cannot_approve_article(self):
        client = auth_client(self.journalist)
        url = reverse('api_article_approve', kwargs={'pk': self.article.pk})
        response = client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_approving_already_approved_article_returns_200(self):
        self.article.approved = True
        self.article.save()
        client = auth_client(self.editor)
        url = reverse('api_article_approve', kwargs={'pk': self.article.pk})
        response = client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('already approved', response.data['detail'])

    def test_approve_nonexistent_article_returns_404(self):
        client = auth_client(self.editor)
        url = reverse('api_article_approve', kwargs={'pk': 99999})
        response = client.post(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ArticleDeleteAPITest(APITestCase):
    def setUp(self):
        self.journalist = make_user('journo_del', CustomUser.Role.JOURNALIST)
        self.other_journalist = make_user('journo_del2', CustomUser.Role.JOURNALIST)
        self.editor = make_user('editor_del', CustomUser.Role.EDITOR)
        self.reader = make_user('reader_del', CustomUser.Role.READER)
        self.article = Article.objects.create(
            title='Article to Delete',
            content='Content.',
            author=self.journalist,
        )

    def test_author_can_delete_own_article(self):
        client = auth_client(self.journalist)
        url = reverse('api_article_detail', kwargs={'pk': self.article.pk})
        response = client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_editor_can_delete_any_article(self):
        article2 = Article.objects.create(title='Another', content='X', author=self.journalist)
        client = auth_client(self.editor)
        url = reverse('api_article_detail', kwargs={'pk': article2.pk})
        response = client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_other_journalist_cannot_delete_article(self):
        client = auth_client(self.other_journalist)
        url = reverse('api_article_detail', kwargs={'pk': self.article.pk})
        response = client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reader_cannot_delete_article(self):
        """
        Readers cannot delete articles. The pending article is hidden from readers
        (404), which is the correct security behaviour — not revealing resource existence.
        For an approved article, the permission check yields 403.
        """
        # Create an approved article so the reader can "see" it, then attempt delete
        approved = Article.objects.create(
            title='Approved Deletable', content='X', author=self.journalist, approved=True
        )
        client = auth_client(self.reader)
        url = reverse('api_article_detail', kwargs={'pk': approved.pk})
        response = client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Subscribed articles API tests
# ---------------------------------------------------------------------------

class SubscribedArticlesAPITest(APITestCase):
    def setUp(self):
        self.publisher = Publisher.objects.create(name='The Observer')
        self.journalist = make_user('journo_sub', CustomUser.Role.JOURNALIST, self.publisher)
        self.editor = make_user('editor_sub', CustomUser.Role.EDITOR)
        self.reader = make_user('reader_sub', CustomUser.Role.READER)
        self.reader.subscribed_publishers.add(self.publisher)

        self.subscribed_article = Article.objects.create(
            title='Publisher Article',
            content='From the publisher.',
            author=self.journalist,
            publisher=self.publisher,
            approved=True,
            approved_at=timezone.now(),
        )
        self.unsubscribed_article = Article.objects.create(
            title='Other Article',
            content='From someone else.',
            author=self.editor,
            approved=True,
            approved_at=timezone.now(),
        )

    def test_reader_sees_only_subscribed_publisher_articles(self):
        client = auth_client(self.reader)
        response = client.get(reverse('api_subscribed_articles'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Publisher Article', titles)
        self.assertNotIn('Other Article', titles)

    def test_reader_with_journalist_subscription_sees_their_articles(self):
        reader2 = make_user('reader_sub2', CustomUser.Role.READER)
        reader2.subscribed_journalists.add(self.journalist)
        client = auth_client(reader2)
        response = client.get(reverse('api_subscribed_articles'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [a['title'] for a in response.data['results']]
        self.assertIn('Publisher Article', titles)

    def test_reader_with_no_subscriptions_sees_empty_list(self):
        reader3 = make_user('reader_sub3', CustomUser.Role.READER)
        client = auth_client(reader3)
        response = client.get(reverse('api_subscribed_articles'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)


# ---------------------------------------------------------------------------
# Newsletter API tests
# ---------------------------------------------------------------------------

class NewsletterAPITest(APITestCase):
    def setUp(self):
        self.journalist = make_user('journo_nl', CustomUser.Role.JOURNALIST)
        self.reader = make_user('reader_nl', CustomUser.Role.READER)
        self.editor = make_user('editor_nl', CustomUser.Role.EDITOR)
        self.article = Article.objects.create(
            title='NL Article', content='Content.', author=self.journalist, approved=True
        )

    def test_journalist_can_create_newsletter(self):
        client = auth_client(self.journalist)
        data = {
            'title': 'Weekly Digest',
            'description': 'Top stories.',
            'article_ids': [self.article.pk],
        }
        response = client.post(reverse('api_newsletter_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Weekly Digest')

    def test_editor_can_create_newsletter(self):
        client = auth_client(self.editor)
        data = {'title': 'Editor Digest', 'description': '', 'article_ids': []}
        response = client.post(reverse('api_newsletter_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reader_can_list_newsletters(self):
        Newsletter.objects.create(title='Public NL', author=self.journalist)
        client = auth_client(self.reader)
        response = client.get(reverse('api_newsletter_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reader_cannot_create_newsletter(self):
        client = auth_client(self.reader)
        data = {'title': 'Fake NL', 'description': '', 'article_ids': []}
        response = client.post(reverse('api_newsletter_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_delete_any_newsletter(self):
        nl = Newsletter.objects.create(title='To Delete', author=self.journalist)
        client = auth_client(self.editor)
        url = reverse('api_newsletter_detail', kwargs={'pk': nl.pk})
        response = client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_journalist_cannot_delete_other_journalists_newsletter(self):
        """
        A journalist attempting to delete another journalist's newsletter receives
        404 — the queryset hides resources they don't own (correct security behaviour).
        """
        other_journo = make_user('journo_nl2', CustomUser.Role.JOURNALIST)
        nl = Newsletter.objects.create(title='Other NL', author=other_journo)
        client = auth_client(self.journalist)
        url = reverse('api_newsletter_detail', kwargs={'pk': nl.pk})
        response = client.delete(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# ---------------------------------------------------------------------------
# Signal / service logic tests (mocked email and X)
# ---------------------------------------------------------------------------

class SignalAndServiceTest(TestCase):
    def setUp(self):
        self.publisher = Publisher.objects.create(name='Signal Publisher')
        self.journalist = make_user('journo_sig', CustomUser.Role.JOURNALIST, self.publisher)
        self.editor = make_user('editor_sig', CustomUser.Role.EDITOR)
        self.reader = make_user('reader_sig', CustomUser.Role.READER)
        self.reader.subscribed_publishers.add(self.publisher)
        self.reader.email = 'reader@example.com'
        self.reader.save()

        self.article = Article.objects.create(
            title='Signal Article',
            content='Content.',
            author=self.journalist,
            publisher=self.publisher,
        )

    @patch('news.services.send_mail')
    def test_notify_subscribers_sends_email_to_subscriber(self, mock_send_mail):
        from news.services import notify_subscribers
        notify_subscribers(self.article)
        mock_send_mail.assert_called_once()
        _, kwargs = mock_send_mail.call_args
        recipient_list = kwargs.get('recipient_list', [])
        self.assertIn('reader@example.com', recipient_list)

    @patch('news.services.send_mail')
    def test_notify_subscribers_no_subscribers_skips_email(self, mock_send_mail):
        from news.services import notify_subscribers
        article2 = Article.objects.create(
            title='Orphan Article', content='No subscribers.', author=self.journalist
        )
        notify_subscribers(article2)
        mock_send_mail.assert_not_called()

    @patch('news.services.requests.post')
    def test_post_to_x_skipped_without_credentials(self, mock_post):
        """No HTTP request when X API credentials are blank."""
        from news.services import post_to_x
        from django.conf import settings
        original = settings.X_API_KEY
        settings.X_API_KEY = ''
        try:
            post_to_x(self.article)
            mock_post.assert_not_called()
        finally:
            settings.X_API_KEY = original

    @patch('news.signals.notify_subscribers')
    @patch('news.signals.post_to_x')
    def test_signal_fires_on_article_approval(self, mock_tweet, mock_email):
        """Saving an approved article triggers the post_save signal handlers."""
        self.article.approved = True
        self.article.approved_by = self.editor
        self.article.approved_at = timezone.now()
        self.article.save()
        mock_email.assert_called_once_with(self.article)
        mock_tweet.assert_called_once_with(self.article)

    @patch('news.signals.notify_subscribers')
    @patch('news.signals.post_to_x')
    def test_signal_does_not_fire_for_title_only_save(self, mock_tweet, mock_email):
        """Saving with update_fields=['title'] must not trigger notifications."""
        self.article.title = 'Updated Title'
        self.article.save(update_fields=['title'])
        mock_email.assert_not_called()
        mock_tweet.assert_not_called()


# ---------------------------------------------------------------------------
# Authentication endpoint tests
# ---------------------------------------------------------------------------

class AuthAPITest(APITestCase):
    def setUp(self):
        self.user = make_user('auth_user', CustomUser.Role.READER)

    def test_obtain_token_success(self):
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'auth_user',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_obtain_token_wrong_password_fails(self):
        response = self.client.post(reverse('token_obtain_pair'), {
            'username': 'auth_user',
            'password': 'WrongPassword',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_creates_user(self):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'role': 'reader',
        }
        response = self.client.post(reverse('api_register'), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CustomUser.objects.filter(username='newuser').exists())

    def test_register_mismatched_passwords_fails(self):
        data = {
            'username': 'newuser2',
            'email': 'new2@example.com',
            'password': 'StrongPass123!',
            'password2': 'Different!',
            'role': 'reader',
        }
        response = self.client.post(reverse('api_register'), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
