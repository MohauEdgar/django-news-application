from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

# Web UI URL patterns
urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Articles
    path('', views.ArticleListView.as_view(), name='article_list'),
    path('articles/new/', views.ArticleCreateView.as_view(), name='article_create'),
    path('articles/<int:pk>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('articles/<int:pk>/edit/', views.ArticleUpdateView.as_view(), name='article_update'),
    path('articles/<int:pk>/delete/', views.ArticleDeleteView.as_view(), name='article_delete'),

    # Editor approval
    path('editor/approval/', views.ApprovalDashboardView.as_view(), name='approval_dashboard'),
    path('editor/approval/<int:pk>/approve/', views.approve_article_view, name='approve_article'),

    # Newsletters
    path('newsletters/', views.NewsletterListView.as_view(), name='newsletter_list'),
    path('newsletters/new/', views.NewsletterCreateView.as_view(), name='newsletter_create'),
    path('newsletters/<int:pk>/', views.NewsletterDetailView.as_view(), name='newsletter_detail'),
    path('newsletters/<int:pk>/edit/', views.NewsletterUpdateView.as_view(), name='newsletter_update'),
    path('newsletters/<int:pk>/delete/', views.NewsletterDeleteView.as_view(), name='newsletter_delete'),

    # REST API — Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/register/', views.RegisterAPIView.as_view(), name='api_register'),

    # REST API — Articles
    path('api/articles/', views.ArticleListCreateAPIView.as_view(), name='api_article_list'),
    path('api/articles/subscribed/', views.SubscribedArticlesAPIView.as_view(), name='api_subscribed_articles'),
    path('api/articles/<int:pk>/', views.ArticleRetrieveUpdateDestroyAPIView.as_view(), name='api_article_detail'),
    path('api/articles/<int:pk>/approve/', views.ArticleApprovalAPIView.as_view(), name='api_article_approve'),

    # REST API — Newsletters
    path('api/newsletters/', views.NewsletterListCreateAPIView.as_view(), name='api_newsletter_list'),
    path('api/newsletters/<int:pk>/', views.NewsletterRetrieveUpdateDestroyAPIView.as_view(), name='api_newsletter_detail'),

    # REST API — Publishers
    path('api/publishers/', views.PublisherListAPIView.as_view(), name='api_publisher_list'),

    # REST API — User profile
    path('api/profile/', views.UserProfileAPIView.as_view(), name='api_profile'),
]
