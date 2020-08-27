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
from tr_ara_aragorn.aragorn_app import AppConfig as AragornApp
from tr_ara_arax.arax_app import AppConfig as ARAXApp
from tr_ara_bte.bte_app import AppConfig as BTEApp
from tr_ara_ncats.ncats_app import AppConfig as NCATSApp
from tr_ara_robokop.robokop_app import AppConfig as RobokopApp
from tr_ara_rtx.rtx_app import AppConfig as RTXApp
from tr_ara_unsecret.unsecret_app import AppConfig as UnsecretApp
from tr_kp_genetics.genetics_app import AppConfig as GeneticsApp
from tr_kp_molecular.molecular_app import AppConfig as MolecularApp
from tr_ars.default_ars_app.ars_app import AppConfig as ARSApp

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ars/', include('tr_ars.urls')),
    #url(r'^example/', include(ARSApp.name)),
    url(AragornApp.regex_path,include(AragornApp.name)),
    url(ARAXApp.regex_path,include(ARAXApp.name)),
    url(BTEApp.regex_path, include(BTEApp.name)),
    url(NCATSApp.regex_path,include(NCATSApp.name)),
    url(RobokopApp.regex_path, include(RobokopApp.name)),
    url(RTXApp.regex_path, include(RTXApp.name)),
    url(UnsecretApp.regex_path, include(UnsecretApp.name)),
    url(GeneticsApp.regex_path,include(GeneticsApp.name)),
    url(MolecularApp.regex_path,include(MolecularApp.name)),
]
