from apps.core.models import AdminScope


def get_scope_for_django_user(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return None
    return AdminScope.objects.filter(django_user=user).prefetch_related('allowed_regions').first()


def filter_by_scope(queryset, user, region_path='region'):
    scope = get_scope_for_django_user(user)
    if not scope or scope.can_manage_all_regions:
        return queryset
    region_ids = scope.allowed_regions.values_list('id', flat=True)
    return queryset.filter(**{f'{region_path}__in': region_ids})


def get_default_scope_region(user):
    scope = get_scope_for_django_user(user)
    if not scope or scope.can_manage_all_regions:
        return None
    return scope.allowed_regions.first()
