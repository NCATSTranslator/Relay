"""tr_sys URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url
from django.contrib import admin
from django.urls import include, path
from tr_ara_unsecret.unsecret_app import AppConfig as UnsecretApp
from tr_ara_arax.arax_app import AppConfig as ARAXApp
from tr_ara_bte.bte_app import AppConfig as BTEApp
from tr_ars.default_ars_app.ars_app import AppConfig as ARSApp

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ars/', include('tr_ars.urls')),
    #url(r'^example/', include(ARSApp.name)),
    url(r'^robokop/', include('tr_ara_robokop.urls')),
    url(BTEApp.regex_path, include(BTEApp.name)),
    url(r'^ncats/',include('tr_ara_ncats.urls')),
    url(UnsecretApp.regex_path, include(UnsecretApp.name)),
    url(ARAXApp.regex_path,include(ARAXApp.name)),
    url(r'^molecular/',include('tr_kp_molecular.urls')),
    url(r'^genetics/',include('tr_kp_genetics.urls'))
]
