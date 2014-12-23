import datetime
import calendar
import logging
import operator
from collections import OrderedDict

import httpagentparser

from google.appengine.ext import ndb
from google.appengine.api import taskqueue
from google.appengine.datastore.datastore_query import Cursor

class Url (ndb.Model):
  url = ndb.StringProperty()
  html_tag = ndb.StringProperty(default='a')
  
  list_id = ndb.StringProperty()
  campaign_id = ndb.StringProperty()
  
  tags = ndb.StringProperty(repeated=True, required=False)
  
  created = ndb.DateTimeProperty(auto_now_add=True)
  
class Stats (ndb.Model):
  list_id = ndb.StringProperty()
  campaign_id = ndb.StringProperty()
  
  total_clicks = ndb.IntegerProperty(default=0)
  total_opens = ndb.IntegerProperty(default=0)
  total_sends = ndb.IntegerProperty(default=0)
  
  clicks = ndb.JsonProperty(compressed=True)
  tags = ndb.JsonProperty(compressed=True, required=False)
  
  opens = ndb.JsonProperty(compressed=True)
  clients = ndb.JsonProperty(compressed=True, required=False)
  urls = ndb.JsonProperty(compressed=True, required=False)
  
  created = ndb.DateTimeProperty(auto_now_add=True)
  last_compiled = ndb.DateTimeProperty(auto_now=True)
  
  def open_rate (self):
    try:
      rate = (self.total_opens / float(self.total_sends)) * 100
      return round(rate)
      
    except:
      return 0
      
  def clients_sorted (self):
    return reversed(sorted(self.clients.iteritems(), key=operator.itemgetter(1)))
    
  def tags_sorted (self):
    tags = reversed(sorted(self.tags.iteritems(), key=operator.itemgetter(1)))
    grouped = OrderedDict()
    totals = {}
    
    for tag in tags:
      temp = tag[0].split(':')
      if len(temp) > 1:
        g = temp[0]
        t = temp[1]
        
      else:
        g = 'Ungrouped'
        t = temp[0]
        
      if grouped.has_key(g):
        grouped[g].append([t, None, tag[1]])
        totals[g] += tag[1]
        
      else:
        grouped[g] = [[t, None, tag[1]]]
        totals[g] = tag[1]
        
    for key in grouped.keys():
      if key != 'Ungrouped':
        total = 0
        for t in grouped[key]:
          total += t[2]
          
        for t in grouped[key]:
          t[1] = round((float(t[2]) / total) * 100, 1)
          
    return grouped.items()
    
  def urls_sorted (self):
    return reversed(sorted(self.urls.iteritems(), key=operator.itemgetter(1)))
    
  def opens_pc (self, count):
    pc = (float(count) / self.total_opens) * 100
    return round(pc, 1)
    
  def clicks_pc (self, count):
    pc = (float(count) / self.total_clicks) * 100
    return round(pc, 1)
    
  def process_track (self, t):
    if t.created.minute % 10 >= 5:
      m = t.created.minute + (10 - (t.created.minute % 10))
      
    else:
      m = t.created.minute - (t.created.minute % 10)
      
    if m == 60:
      time = t.created.replace(minute=0, second=0, microsecond=0)
      time = time + datetime.timedelta(hours=1)
      
    else:
      time = t.created.replace(minute=m, second=0, microsecond=0)
      
    key = calendar.timegm(time.timetuple())

    if t.ttype == 'click':
      if self.temp_clicks.has_key(key):
        self.temp_clicks[key] += 1
      else:
        self.temp_clicks[key] = 1

      if t.tags:
        for tag in t.tags:
          if tag in self.tags:
            self.tags[tag] += 1
            
          else:
            self.tags[tag] = 1
            
      url = t.url.get().url
      if url in self.urls:
        self.urls[url] += 1
        
      else:
        self.urls[url] = 1
        
    elif t.ttype == 'open':
      if self.temp_opens.has_key(key):
        self.temp_opens[key] += 1
      else:
        self.temp_opens[key] = 1

      key = 'Other'
      if t.email_client:
        key = t.email_client
        
      elif t.browser_os:
        key = t.browser_os
        
      if key in self.clients:
        self.clients[key] += 1
        
      else:
        self.clients[key] = 1
        
  def sort_data (self, ptype):
    tmp = getattr(self, 'temp_'+ptype)
    keys = tmp.keys()
    keys.sort()
    perm = []
    
    for k in keys:
      perm.append((k, tmp[k]))
      
    setattr(self, ptype, perm)
    
  def process (self, cursor=None):

    if cursor:
        cursor = Cursor(urlsafe=cursor)

    total_clicks = 0
    total_opens = 0
    
    self.temp_clicks = {}
    self.temp_opens = {}
    if cursor == None: #skip all cursor continuations, these values are already init'd
      self.tags = {}
      self.urls = {}
      self.clients = {}
      self.clicks = []
      self.opens = []
      self.total_sends = 0
      self.total_clicks = 0
      self.total_opens = 0

      from bulkmail.api.models import Campaign
      c = Campaign.query(Campaign.campaign_id == self.campaign_id, Campaign.list_id == self.list_id).get()
      
      for key in c.send_data:
        sd = key.get()
        self.total_sends += len(sd.data)

    tracks, cursor, more = Track.query(
        Track.list_id == self.list_id,
        Track.campaign_id == self.campaign_id,
        ndb.OR(Track.ttype == 'click', Track.ttype == 'open')
      ).order(Track._key).fetch_page(100, start_cursor=cursor)

    for t in tracks:
      self.process_track(t)
      if t.ttype == 'click':
        total_clicks += 1
      elif t.ttype == 'open':
        total_opens += 1

    #set total_clicks/total_opens
    self.total_clicks = self.total_clicks + total_clicks
    self.total_opens = self.total_opens + total_opens
    #set clicks/opens
    self.sort_data('clicks')
    self.sort_data('opens')

    self.put()

    if more and cursor:
      taskqueue.add(
        url='/api/compile-stats',
        params={
          'list_id': self.list_id,
          'campaign_id': self.campaign_id,
          'key': self.key.urlsafe(),
          'cursor': cursor.urlsafe()
        },
        queue_name='stats'
      )




WEB_CLIENTS = (
  ('google.com', 'GMail'),
  ('yahoo.com', 'Yahoo'),
  ('live.com', 'Outlook.com'),
)

EMAIL_CLIENTS = (
  ('Outlook', 'Outlook'),
)

class Track (ndb.Model):
  ttype = ndb.StringProperty() #open, click, image
  
  list_id = ndb.StringProperty()
  campaign_id = ndb.StringProperty()
  
  user_agent = ndb.StringProperty(required=False)
  referer = ndb.StringProperty(required=False)
  
  browser_os = ndb.StringProperty(required=False)
  browser_name = ndb.StringProperty(required=False)
  browser_version = ndb.IntegerProperty(required=False)
  email_client = ndb.StringProperty(required=False)
  
  email = ndb.StringProperty(required=False)
  url = ndb.KeyProperty(kind=Url, required=False)
  
  tags = ndb.StringProperty(repeated=True, required=False)
  
  created = ndb.DateTimeProperty(auto_now_add=True)
  
  def detect_browser (self):
    if self.user_agent:
      for client in EMAIL_CLIENTS:
        if client[0] in self.user_agent:
          self.email_client = client[1]
          break
          
      b = httpagentparser.detect(self.user_agent)
      if 'dist' in b and 'name' in b['dist']:
        self.browser_os = b['dist']['name']
        
      elif 'os' in b and 'name' in b['os']:
        self.browser_os = b['os']['name']
        
      if 'browser' in b:
        if 'name' in b['browser']:
          self.browser_name = b['browser']['name']
          
        if 'version' in b['browser']:
          try:
            self.browser_version = int(b['browser']['version'].split('.')[0])
            
          except:
            pass
            
    if self.referer:
      for client in WEB_CLIENTS:
        if client[0] in self.referer:
          self.email_client = client[1]
          break
          