import hmac
import base64
import hashlib
import datetime
import urllib
import logging
import traceback
import json
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from google.appengine.api import urlfetch
from google.appengine.api import taskqueue

from .base import BaseEmailer


def mailgun_send(**kwargs):
  count = 0
  email = kwargs['email']
  del kwargs['email']

  while 1:
    count += 1

    try:
      result = urlfetch.fetch(**kwargs)

    except:
      logging.error('Send Error: ' + email)
      logging.error('Try: %d' % count)
      logging.error(traceback.format_exc())

    else:
      if result.status_code == 200:
        break

      else:
        logging.error('Send Error: ' + email)
        logging.error('Try: %d' % count)
        logging.error('Status Code: %d' % result.status_code)
        logging.error(result.content)

    if count >= 3:
      logging.error(kwargs)

      raise Exception("Send Failed")

    time.sleep(1)


class EMailer(BaseEmailer):
  def __init__(self, *args, **kwargs):
    super(EMailer, self).__init__(*args, **kwargs)


  def headers(self, unsubscribe):
    h = {
      'h:List-Id': self.list_id,
      'h:List-Unsubscribe': '<%s>' % unsubscribe,
    }
    return h

  def send(self, email, context, log=True):
    if self.skip(email):
      return None

    key = self.generate_key(email)
    context['key'] = key
    context['unsubscribe'] = self.unsubscribe_url(email, key)

    self.frm = '%s <mailer@%s>' % (self.from_name, self.mail_domain)

    form_data = {"from": self.frm,
                 "to": email,
                 "subject": self.subject,
                 "text": self.render(self.text_tpl, context),
                 "h:Reply-To": self.reply_to}
    form_data.update(self.headers(context['unsubscribe']))

    if self.html_tpl:
      form_data.update({"html": self.render(self.html_tpl, context, True)})

    #for some reason, we're receiving unicode here and urlencode is prone to failure because
    #it expects strings; so we're encoding everything into utf-8
    for k, v in form_data.iteritems():
      form_data[k] = unicode(v).encode('utf-8')
    form_data = urllib.urlencode(form_data)

    kwargs = {
      'email': email,
      'url': "https://api.mailgun.net/v2/%s/messages" % self.mail_domain,
      'payload': form_data,
      'method': urlfetch.POST,
      'headers': {
        'Content-type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic %s' % base64.b64encode("api:key-%s" % settings.MAILGUN_API_KEY)
      },
      'deadline': 60,
    }

    taskqueue.add(url='/mailgun/send', params={'data': json.dumps(kwargs)}, queue_name='mailgun')

    if log:
      self.log_send(email)

  def close(self):
    pass
  