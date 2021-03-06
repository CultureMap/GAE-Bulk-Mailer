import logging

from django import http

from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from .models import Url, Track
from ..mailers.base import emailer_key
from ..api.models import Campaign

TRANSPARENT_1_PIXEL_GIF = "\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"

def verify_email (target):
  def wrapper (*args, **kwargs):
    request = args[0]
    if len(args) == 3:
      list_id = args[1]
      campaign_id = args[2]
      
    else:
      try:
        obj = ndb.Key(urlsafe=args[1]).get()
      except:
        raise http.Http404
        
      if obj:
        list_id = obj.list_id
        campaign_id = obj.campaign_id
        
      else:
        raise http.Http404
        
    email = request.GET.get('email', '')
    key = request.GET.get('key', '')
    
    if email and key:
      cmpgn = Campaign.query(Campaign.list_id==list_id, Campaign.campaign_id==campaign_id).get()
      if cmpgn:
        if key == emailer_key(email, cmpgn.list_id, cmpgn.campaign_id, cmpgn.salt):
          if len(args) == 3:
            kwargs['email'] = email
            return target(*args, **kwargs)
            
          else:
            kwargs['email'] = email
            return target(request, obj, **kwargs)
            
    
    if len(args) == 3:
      return target(*args, **kwargs)
      
    return target(request, obj, **kwargs)
    
  return wrapper
  
def ua_string (request):
  if request.META.has_key('HTTP_USER_AGENT'):
    #limit the string to 500 chars since we will be saving this in a String field
    return request.META['HTTP_USER_AGENT'][:500]
    
  return None
  
def refer_string (request):
  if request.META.has_key('HTTP_REFERER'):
    #limit the string to 500 chars since we will be saving this in a String field
    return request.META['HTTP_REFERER'][:500]
    
  return None
  
@verify_email
def open_pixel (request, list_id, campaign_id, email=None):
  ua = ua_string(request)
  refer = refer_string(request)
  
  if email:
    email = email.lower()
    t = Track(ttype='open', list_id=list_id, campaign_id=campaign_id, email=email, user_agent=ua, referer=refer)

    taskqueue.add(url='/api/process-open', params={'email': email, 'list_id': list_id, 'campaign_id': campaign_id}, queue_name='stats')

  else:
    t = Track(ttype='open', list_id=list_id, campaign_id=campaign_id, user_agent=ua, referer=refer)
    
  t.detect_browser()
  t.put()

  return http.HttpResponse(TRANSPARENT_1_PIXEL_GIF, content_type='image/gif')
  
@verify_email
def url_redirect (request, url, email=None):
  ua = ua_string(request)
  refer = refer_string(request)
  
  ttype = 'click'
  if url.html_tag == 'img':
    ttype = 'image'
    
  if email:
    t = Track(
      ttype=ttype,
      list_id=url.list_id,
      campaign_id=url.campaign_id,
      email=email.lower(),
      url=url.key,
      tags=url.tags,
      user_agent=ua,
      referer=refer,
    )
    
  else:
    t = Track(
      ttype=ttype,
      list_id=url.list_id,
      campaign_id=url.campaign_id,
      url=url.key,
      tags=url.tags,
      user_agent=ua,
      referer=refer,
    )
    
  t.detect_browser()
  t.put()
  
  return http.HttpResponseRedirect(url.url)
  