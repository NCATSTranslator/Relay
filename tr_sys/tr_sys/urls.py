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
import logging
import traceback
from django.conf import settings
from django.urls import include, re_path
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, reverse
from tr_ara_aragorn.aragorn_app import AppConfig as AragornApp
from tr_ara_arax.arax_app import AppConfig as ARAXApp
from tr_ara_bte.bte_app import AppConfig as BTEApp
from tr_ara_explanatory.explanatory_app import AppConfig as ExplanatoryApp
from tr_ara_improving.improving_app import AppConfig as ImprovingApp
from tr_ara_ncats.ncats_app import AppConfig as NCATSApp
from tr_ara_robokop.robokop_app import AppConfig as RobokopApp
from tr_ara_aragorn_exp.aragorn_exp_app import AppConfig as AragornExpApp
from tr_ara_unsecret.unsecret_app import AppConfig as UnsecretApp
from tr_ara_wfr.wfr_app import AppConfig as WfrApp
from tr_ara_explanatory_exp.explanatory_exp_app import AppConfig as ExplanatoryExpApp
from tr_kp_genetics.genetics_app import AppConfig as GeneticsApp
from tr_kp_molecular.molecular_app import AppConfig as MolecularApp
from tr_kp_cam.cam_app import AppConfig as CamApp
from tr_kp_textmining.textmining_app import AppConfig as TextMiningApp
from tr_kp_openpredict.openpredict_app import AppConfig as OpenPredictApp
from tr_kp_cohd.cohd_app import AppConfig as COHDApp
from tr_kp_chp.chp_app import AppConfig as ChpApp
from tr_kp_icees_kg.icees_kg_app import AppConfig as IceesKgApp
from tr_ars.default_ars_app.ars_app import AppConfig as ARSApp

logger = logging.getLogger(__name__)

patterns = [
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^ars/', include('tr_ars.urls')),
    #url(r'^example/', include(ARSApp.name)),
    re_path(AragornApp.regex_path, include(AragornApp.name)),
    re_path(ARAXApp.regex_path, include(ARAXApp.name)),
    re_path(BTEApp.regex_path, include(BTEApp.name)),
    re_path(ExplanatoryApp.regex_path,include(ExplanatoryApp.name)),
    re_path(ExplanatoryExpApp.regex_path, include(ExplanatoryExpApp.name)),
    re_path(ImprovingApp.regex_path, include(ImprovingApp.name)),
    re_path(NCATSApp.regex_path, include(NCATSApp.name)),
    re_path(RobokopApp.regex_path, include(RobokopApp.name)),
    re_path(AragornExpApp.regex_path, include(AragornExpApp.name)),
    re_path(WfrApp.regex_path, include(WfrApp.name)),
    re_path(IceesKgApp.regex_path, include(IceesKgApp.name)),
    re_path(UnsecretApp.regex_path, include(UnsecretApp.name)),
    re_path(GeneticsApp.regex_path, include(GeneticsApp.name)),
    re_path(MolecularApp.regex_path, include(MolecularApp.name)),
    re_path(CamApp.regex_path, include(CamApp.name)),
    re_path(TextMiningApp.regex_path, include(TextMiningApp.name)),
    re_path(OpenPredictApp.regex_path, include(OpenPredictApp.name)),
    re_path(COHDApp.regex_path, include(COHDApp.name)),
    re_path(ChpApp.regex_path, include(ChpApp.name))
]

def base_index(req):
    data = dict()
    data['name'] = 'NCATS Biomedical Data Translator Relay Server'
    data['entries'] = []
    for item in patterns[1:]:
        try:
            data['entries'].append(req.build_absolute_uri(item.pattern))
        except Exception as e:
            logger.error("Unexpected error 9: {}".format(traceback.format_exception(type(e), e, e.__traceback__)))
            data['entries'].append(req.build_absolute_uri() + str(item.pattern).replace('^', ''))

    for idx, element in enumerate(data['entries']):
        data['entries'][idx] = element.replace('%5E', '')
        
    return HttpResponse(json.dumps(data, indent=2),
                        content_type='application/json', status=200)

urlpatterns = [re_path('^$', base_index, name='server-top')] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
for pattern in patterns:
    urlpatterns.append(pattern)
