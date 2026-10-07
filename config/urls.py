from django.contrib.auth import views as auth_views
from django.urls import path, include
from contas.urls import paginas_urlpatterns

urlpatterns = [
    path("api/", include("contas.urls")),
    path("login/", auth_views.LoginView.as_view(template_name="contas/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
] + paginas_urlpatterns