from django.urls import path
from .views import (
    CSVUploadAndAnalysisView, 
    SignupView, 
    LoginView, 
    AdminLoginView, 
    PurchaseProView, 
    SubscriptionListView,
    AdminUserListView,
    AdminUserUpdateView,
    AdminUserDeleteView
)

urlpatterns = [
    path('upload-csv/', CSVUploadAndAnalysisView.as_view(), name='upload-csv'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('admin-login/', AdminLoginView.as_view(), name='admin-login'),
    path('purchase-pro/', PurchaseProView.as_view(), name='purchase-pro'),
    path('subscriptions/', SubscriptionListView.as_view(), name='subscriptions'),
    
    # Admin CRUD
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', AdminUserUpdateView.as_view(), name='admin-user-update'),
    path('admin/users/<int:pk>/delete/', AdminUserDeleteView.as_view(), name='admin-user-delete'),
]
