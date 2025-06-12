from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserProfile, InterestTag
from .models import UserTermAgreement

class UserTermAgreementInline(admin.StackedInline):
    model = UserTermAgreement
    can_delete = False
    verbose_name_plural = '약관 동의'
    fk_name = 'user'  # User와 OneToOne일 경우

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = '프로필'
    fk_name = 'user'  # OneToOneField일 때 필수

class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        (None, {'fields': ('nickname', 'name')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('nickname', 'name')}),
    )
    list_display = ('username', 'email', 'name', 'nickname', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'name', 'nickname')
    inlines = [UserProfileInline, UserTermAgreementInline]


admin.site.register(User, UserAdmin)
admin.site.register(InterestTag)
