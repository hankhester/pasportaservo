from itsdangerous import URLSafeTimedSerializer, BadTimeSignature, SignatureExpired

from django.views import generic
from django.db import transaction
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _

from hosting.models import Place


class UniqueLinkView(generic.TemplateView):
    def get(self, request, *args, **kwargs):
        self.token = kwargs.pop('token')
        s = URLSafeTimedSerializer(settings.SECRET_KEY, salt=settings.SALT)
        try:
            payload = s.loads(self.token, max_age=3600*24*30*2)  # 2 months
        except SignatureExpired:
            self.template_name = 'links/signature_expired.html'
        except BadTimeSignature:
            self.template_name = 'links/bad_time_signature.html'
        else:
            return self.redirect(request, payload, *args, **kwargs)
        return super().get(request, *args, **kwargs)

    def redirect(self, request, payload, *args, **kwargs):
        try:
            action = payload['action']
        except KeyError:
            self.template_name = 'links/invalid_link.html'
            return super().get(request, *args, **kwargs)
        return getattr(self, 'redirect_'+action)(request, payload)

    def redirect_confirm(self, request, payload):
        place = get_object_or_404(Place, pk=payload['place'])
        if place.confirmed and place.owner.confirmed:
            return HttpResponseRedirect(reverse('already_confirmed'))
        with transaction.atomic():
            place.confirmed = True
            place.save()
            place.owner.confirmed = True
            place.owner.save()
            place.owner.phones.update(confirmed=True)
            place.owner.website_set.update(confirmed=True)
        return HttpResponseRedirect(reverse('confirmed'))

    def redirect_update(self, request, payload):
        place = get_object_or_404(Place, pk=payload['place'])
        place.owner.user.backend = settings.AUTHENTICATION_BACKENDS[0]
        login(request, place.owner.user)
        messages.success(request, _("You've been automatically logged in. Happy editing!"))
        return HttpResponseRedirect(place.owner.get_absolute_url())

unique_link = UniqueLinkView.as_view()


class ConfirmedView(generic.TemplateView):
    template_name = 'links/confirmed.html'

confirmed = ConfirmedView.as_view()


class AlreadyConfirmedView(generic.TemplateView):
    template_name = 'links/already_confirmed.html'

already_confirmed = AlreadyConfirmedView.as_view()
