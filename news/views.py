"""
Views for the News Application.

Contains:
  - Template-based views for the web UI (article list, detail, approval dashboard).
  - Django REST Framework API views for the RESTful API.
"""

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CustomUser, Article, Newsletter, Publisher
from .permissions import IsEditor, IsJournalist, IsJournalistOrEditor, IsOwnerOrEditor
from .serializers import (
    ArticleSerializer, ArticleApprovalSerializer, NewsletterSerializer,
    PublisherSerializer, UserSerializer, RegisterSerializer,
)
from .services import notify_subscribers, post_to_x


# ---------------------------------------------------------------------------
# Helper mixins for template views
# ---------------------------------------------------------------------------

class EditorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict template views to Editor-role users."""
    def test_func(self):
        return self.request.user.role == CustomUser.Role.EDITOR


class JournalistOrEditorMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict template views to Journalist or Editor users."""
    def test_func(self):
        return self.request.user.role in (
            CustomUser.Role.JOURNALIST, CustomUser.Role.EDITOR
        )


# ---------------------------------------------------------------------------
# Authentication template views
# ---------------------------------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect('article_list')
    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'article_list'))
        error = 'Invalid username or password.'
    return render(request, 'news/login.html', {'error': error})


@login_required
def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('login')


def register_view(request):
    from .forms import CustomUserCreationForm
    if request.user.is_authenticated:
        return redirect('article_list')
    form = CustomUserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Account created successfully!')
        return redirect('article_list')
    return render(request, 'news/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Article template views
# ---------------------------------------------------------------------------

class ArticleListView(LoginRequiredMixin, ListView):
    model = Article
    template_name = 'news/article_list.html'
    context_object_name = 'articles'

    def get_queryset(self):
        user = self.request.user
        if user.role in (CustomUser.Role.EDITOR, CustomUser.Role.JOURNALIST):
            return Article.objects.select_related('author', 'publisher').all()
        # Readers see only approved articles
        return Article.objects.filter(approved=True).select_related('author', 'publisher')


class ArticleDetailView(LoginRequiredMixin, DetailView):
    model = Article
    template_name = 'news/article_detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        user = self.request.user
        if user.role in (CustomUser.Role.EDITOR, CustomUser.Role.JOURNALIST):
            return Article.objects.all()
        return Article.objects.filter(approved=True)


class ArticleCreateView(JournalistOrEditorMixin, CreateView):
    model = Article
    template_name = 'news/article_form.html'
    fields = ['title', 'content', 'publisher']
    success_url = reverse_lazy('article_list')

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, 'Article submitted for review.')
        return super().form_valid(form)


class ArticleUpdateView(JournalistOrEditorMixin, UpdateView):
    model = Article
    template_name = 'news/article_form.html'
    fields = ['title', 'content', 'publisher']
    success_url = reverse_lazy('article_list')

    def get_queryset(self):
        user = self.request.user
        if user.role == CustomUser.Role.EDITOR:
            return Article.objects.all()
        return Article.objects.filter(author=user)


class ArticleDeleteView(JournalistOrEditorMixin, DeleteView):
    model = Article
    template_name = 'news/article_confirm_delete.html'
    success_url = reverse_lazy('article_list')

    def get_queryset(self):
        user = self.request.user
        if user.role == CustomUser.Role.EDITOR:
            return Article.objects.all()
        return Article.objects.filter(author=user)


# ---------------------------------------------------------------------------
# Editor approval dashboard
# ---------------------------------------------------------------------------

class ApprovalDashboardView(EditorRequiredMixin, ListView):
    """Editors see all pending (unapproved) articles here."""
    model = Article
    template_name = 'news/approval_dashboard.html'
    context_object_name = 'articles'
    queryset = Article.objects.filter(approved=False).select_related('author', 'publisher')


@login_required
def approve_article_view(request, pk):
    """
    Approve a single article — Editor only.
    Option 2: notification logic handled directly in the view (no signals for approval).
    """
    if request.user.role != CustomUser.Role.EDITOR:
        messages.error(request, 'Only editors can approve articles.')
        return redirect('article_list')
    article = get_object_or_404(Article, pk=pk)
    if request.method == 'POST':
        if not article.approved:
            article.approved = True
            article.approved_by = request.user
            article.approved_at = timezone.now()
            article.save()
            notify_subscribers(article)
            post_to_x(article)
            messages.success(
                request,
                f'Article "{article.title}" approved and subscribers notified.',
            )
        else:
            messages.info(request, 'Article was already approved.')
        return redirect('approval_dashboard')
    return render(request, 'news/approve_article.html', {'article': article})


# ---------------------------------------------------------------------------
# Newsletter template views
# ---------------------------------------------------------------------------

class NewsletterListView(LoginRequiredMixin, ListView):
    model = Newsletter
    template_name = 'news/newsletter_list.html'
    context_object_name = 'newsletters'
    queryset = Newsletter.objects.select_related('author').prefetch_related('articles').all()


class NewsletterDetailView(LoginRequiredMixin, DetailView):
    model = Newsletter
    template_name = 'news/newsletter_detail.html'
    context_object_name = 'newsletter'


class NewsletterCreateView(JournalistOrEditorMixin, CreateView):
    model = Newsletter
    template_name = 'news/newsletter_form.html'
    fields = ['title', 'description', 'articles']
    success_url = reverse_lazy('newsletter_list')

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, 'Newsletter created.')
        return super().form_valid(form)


class NewsletterUpdateView(JournalistOrEditorMixin, UpdateView):
    model = Newsletter
    template_name = 'news/newsletter_form.html'
    fields = ['title', 'description', 'articles']
    success_url = reverse_lazy('newsletter_list')

    def get_queryset(self):
        user = self.request.user
        if user.role == CustomUser.Role.EDITOR:
            return Newsletter.objects.all()
        return Newsletter.objects.filter(author=user)


class NewsletterDeleteView(JournalistOrEditorMixin, DeleteView):
    model = Newsletter
    template_name = 'news/newsletter_confirm_delete.html'
    success_url = reverse_lazy('newsletter_list')

    def get_queryset(self):
        user = self.request.user
        if user.role == CustomUser.Role.EDITOR:
            return Newsletter.objects.all()
        return Newsletter.objects.filter(author=user)


# ---------------------------------------------------------------------------
# REST API Views
# ---------------------------------------------------------------------------

class RegisterAPIView(APIView):
    """POST /api/register/ — create a new user account."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {'message': 'Account created.', 'user_id': user.pk},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ArticleListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/articles/  — list all approved articles (any authenticated user).
    POST /api/articles/  — create a new article (journalists only).
    """
    serializer_class = ArticleSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJournalist()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return Article.objects.filter(approved=True).select_related('author', 'publisher')


class SubscribedArticlesAPIView(generics.ListAPIView):
    """
    GET /api/articles/subscribed/ — articles from the reader's subscribed publishers/journalists.
    """
    serializer_class = ArticleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            Article.objects.filter(approved=True)
            .filter(
                Q(author__in=user.subscribed_journalists.all())
                | Q(publisher__in=user.subscribed_publishers.all())
            )
            .select_related('author', 'publisher')
            .distinct()
        )


class ArticleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/articles/<id>/  — retrieve an article.
    PUT    /api/articles/<id>/  — update (editors or article author).
    DELETE /api/articles/<id>/  — delete (editors or article author).
    """
    serializer_class = ArticleSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsOwnerOrEditor()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role in (CustomUser.Role.EDITOR, CustomUser.Role.JOURNALIST):
            return Article.objects.all()
        return Article.objects.filter(approved=True)


class ArticleApprovalAPIView(APIView):
    """POST /api/articles/<id>/approve/ — approve an article (editors only)."""
    permission_classes = [IsEditor]

    def post(self, request, pk):
        article = get_object_or_404(Article, pk=pk)
        if article.approved:
            return Response({'detail': 'Article is already approved.'}, status=status.HTTP_200_OK)
        article.approved = True
        article.approved_by = request.user
        article.approved_at = timezone.now()
        # update_fields ensures signal fires only for these fields
        article.save(update_fields=['approved', 'approved_by', 'approved_at'])
        return Response(ArticleSerializer(article).data, status=status.HTTP_200_OK)


class NewsletterListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/newsletters/  — list all newsletters.
    POST /api/newsletters/  — create a newsletter (journalists/editors).
    """
    serializer_class = NewsletterSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJournalistOrEditor()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        return Newsletter.objects.select_related('author').prefetch_related('articles').all()


class NewsletterRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = NewsletterSerializer

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsJournalistOrEditor()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            # Editors can modify any newsletter; journalists only their own
            if user.role == CustomUser.Role.EDITOR:
                return Newsletter.objects.all()
            return Newsletter.objects.filter(author=user)
        return Newsletter.objects.all()


class PublisherListAPIView(generics.ListAPIView):
    """GET /api/publishers/ — list all publishers."""
    serializer_class = PublisherSerializer
    queryset = Publisher.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class UserProfileAPIView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/profile/ — view or update the authenticated user's profile."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
