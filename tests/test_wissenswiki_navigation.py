import os

import django
from django.test import RequestFactory, override_settings
from django.template.loader import render_to_string

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from ki_knowledge.django_site.context_processors import wissenswiki_link


@override_settings(ALLOWED_HOSTS=["127.0.0.1", "192.168.2.205", "example.test"])
def test_link_uses_browser_host_for_local_or_lan():
    factory = RequestFactory()
    request = factory.get("/", HTTP_HOST="192.168.2.205:8000")
    assert wissenswiki_link(request)["wissenswiki_url"] == "http://192.168.2.205:8765/workspace/"
    html = render_to_string("base.html", wissenswiki_link(request))
    assert 'href="http://192.168.2.205:8765/workspace/"' in html
    assert "Wissenswiki</a>" in html
    assert wissenswiki_link(factory.get("/", HTTP_HOST="example.test:8000"))["wissenswiki_url"] == ""
