import base64
import random
import hashlib

from ..utils import cached_method
from ..tracking.models import Stats

from google.appengine.ext import ndb

class ApiKey (ndb.Model):
  name = ndb.StringProperty(required=True)
  akey = ndb.StringProperty(required=True)
  created = ndb.DateTimeProperty(auto_now_add=True)
  created_by = ndb.UserProperty(required=True)
  
def generate_key ():
  while 1:
    akey = base64.b64encode(hashlib.sha512( str(random.getrandbits(256)) ).digest(), random.choice(['rA','aZ','gQ','hH','hG','aR','DD'])).rstrip('==')
    if ApiKey.query(ApiKey.akey == akey).count() == 0:
      break
    
  return akey
  
def generate_salt (dt):
  return str(dt) + str(random.getrandbits(50))
  
class SendLog (ndb.Model):
  email = ndb.StringProperty()
  list_id = ndb.StringProperty(required=True)
  campaign_id = ndb.StringProperty(required=True)
  
  created = ndb.DateTimeProperty(auto_now_add=True)
  
class SendData (ndb.Model):
  data = ndb.JsonProperty(compressed=True)
  created = ndb.DateTimeProperty(auto_now_add=True)
  
class Campaign (ndb.Model):
  subject = ndb.StringProperty(required=True)
  reply_to = ndb.StringProperty(required=True)
  from_name = ndb.StringProperty(required=False)
  
  html = ndb.TextProperty(required=False)
  text = ndb.TextProperty(required=True)
  
  list_id = ndb.StringProperty(required=True)
  campaign_id = ndb.StringProperty(required=True)
  mail_domain = ndb.StringProperty(required=False)
  
  created = ndb.DateTimeProperty(auto_now_add=True)
  
  sent = ndb.DateTimeProperty(required=False)
  send = ndb.DateTimeProperty(required=False)
  
  send_data = ndb.KeyProperty(kind=SendData, repeated=True)
  
  salt = ndb.StringProperty(required=True)
  
  analytics = ndb.StringProperty(required=False)
  
  @cached_method
  def stats (self):
    return Stats.query(Stats.list_id == self.list_id, Stats.campaign_id == self.campaign_id).get()
    #return {
    #  'clicks': [[1196463600000, 0], [1196550000000, 0], [1196636400000, 0], [1196722800000, 77], [1196809200000, 3636], [1196895600000, 3575]],
    #  'total_clicks': 10,
    #  'total_opens': 20,
    #}
    
class Unsubscribe (ndb.Model):
  email = ndb.StringProperty()
  list_id = ndb.StringProperty()
  campaign_id = ndb.StringProperty()
  created = ndb.DateTimeProperty(auto_now_add=True)
  
class Bounce (ndb.Model):
  original_from = ndb.StringProperty()
  original_to = ndb.StringProperty()
  original_subject = ndb.StringProperty()
  original_text = ndb.TextProperty()
  
  notification_from = ndb.StringProperty()
  notification_to = ndb.StringProperty()
  notification_subject = ndb.StringProperty()
  notification_text = ndb.TextProperty()
  
  raw_message = ndb.TextProperty()
  
  list_id = ndb.StringProperty()
  campaign_id = ndb.StringProperty()
  
  created = ndb.DateTimeProperty(auto_now_add=True)
  
  reported = ndb.BooleanProperty(default=False)
  
  btype = ndb.StringProperty(default='bounce')
  