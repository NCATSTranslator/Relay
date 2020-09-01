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
import json
from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, reverse
from tr_ara_aragorn.aragorn_app import AppConfig as AragornApp
from tr_ara_arax.arax_app import AppConfig as ARAXApp
from tr_ara_bte.bte_app import AppConfig as BTEApp
from tr_ara_ncats.ncats_app import AppConfig as NCATSApp
from tr_ara_robokop.robokop_app import AppConfig as RobokopApp
from tr_ara_unsecret.unsecret_app import AppConfig as UnsecretApp
from tr_kp_genetics.genetics_app import AppConfig as GeneticsApp
from tr_kp_molecular.molecular_app import AppConfig as MolecularApp
from tr_ars.default_ars_app.ars_app import AppConfig as ARSApp

patterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^ars/', include('tr_ars.urls')),
    #url(r'^example/', include(ARSApp.name)),
    url(AragornApp.regex_path,include(AragornApp.name)),
    url(ARAXApp.regex_path,include(ARAXApp.name)),
    url(BTEApp.regex_path, include(BTEApp.name)),
    url(NCATSApp.regex_path,include(NCATSApp.name)),
    url(RobokopApp.regex_path, include(RobokopApp.name)),
    url(UnsecretApp.regex_path, include(UnsecretApp.name)),
    url(GeneticsApp.regex_path,include(GeneticsApp.name)),
    url(MolecularApp.regex_path,include(MolecularApp.name)),
]

def base_index(req):
    data = dict()
    data['name'] = 'NCATS Biomedical Data Translator Relay Server'
    data['entries'] = []
    for item in patterns[1:]:
        try:
            data['entries'].append(req.build_absolute_uri(reverse(item.name)))
        except:
            data['entries'].append(req.build_absolute_uri() + str(item.pattern).replace('^', ''))
    return HttpResponse(json.dumps(data, indent=2),
                        content_type='application/json', status=200)

urlpatterns = [url('^$', base_index, name='server-top')] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
for pattern in patterns:
    urlpatterns.append(pattern)
