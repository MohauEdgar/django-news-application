from rest_framework.permissions import BasePermission
from .models import CustomUser


class IsReader(BasePermission):
    """Allow access only to users with the Reader role."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == CustomUser.Role.READER)


class IsJournalist(BasePermission):
    """Allow access only to users with the Journalist role."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == CustomUser.Role.JOURNALIST)


class IsEditor(BasePermission):
    """Allow access only to users with the Editor role."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == CustomUser.Role.EDITOR)


class IsJournalistOrEditor(BasePermission):
    """Allow access to journalists and editors."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated
            and request.user.role in (CustomUser.Role.JOURNALIST, CustomUser.Role.EDITOR)
        )


class IsOwnerOrEditor(BasePermission):
    """Object-level: allow the article author or any editor to modify."""
    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.role == CustomUser.Role.EDITOR:
            return True
        return obj.author == request.user
