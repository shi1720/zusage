"""Live workspace regression run. Creates and removes an isolated QA account.

Run with --url and --out. LLM_API_KEY must contain an Apertus key to
include validation, encryption and personal-key generation checks.
"""
import argparse
import json
import os
import secrets
from pathlib import Path
import httpx
parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8080')
parser.add_argument('--out',default='workspace-tests.json')
args=parser.parse_args()
url=args.url
default_key=os.environ.get('LLM_API_KEY','')
results=[]
with httpx.Client(base_url=url,timeout=60) as c:
 def get(p):r=c.get(p);r.raise_for_status();return r.json()
 def post(p,d=None):r=c.post(p,json=d);r.raise_for_status();return r.json()
 def patch(p,d):r=c.patch(p,json=d);r.raise_for_status();return r.json()
 username='qa-'+secrets.token_hex(5)
 try:
  post('/api/auth/register',{'username':username,'password':'qa-only-strong-password','display_name':'QA Learner'})
  assert get('/api/me')['ui_lang']=='en'
  app=post('/api/applications',{'company':'Calanda QA Care','title':'Healthcare apprenticeship','occupation_id':'fage_efz','posting':'We support elderly residents with daily activities. Apprentices work in a supervised team. We value patience and clear communication.','status':'applied'})
  c.put('/api/me/profile',json={'data':{'age':16,'school':'Secondary school','experience':'I completed a trial day at a care home and helped a resident with lunch.','stories':[{'title':'Helping with lunch','text':'I listened patiently, asked what she needed and helped her feel comfortable.'}]}}).raise_for_status()
  for lang in ['en','de','fr','it']:
   patch('/api/me',{'ui_lang':lang})
   draft=post('/api/workspace/generate',{'application_id':app['id'],'kind':'cover_letter'})
   prep=post('/api/workspace/generate',{'application_id':app['id'],'kind':'prep'})
   assert draft['contents'] and prep['contents']
   assert not draft['fallback'] and not prep['fallback'],(lang,draft,prep)
   results.append({'language':lang,'draft':'pass','prep':'pass','model':draft['model']})
  captured=post('/api/workspace/capture',{'text':'Calanda Care in Chur offers a Healthcare Assistant EFZ apprenticeship. Support residents with daily care in a supervised team. We value patience, respect and clear communication.'})
  assert captured['company'] and captured['posting']
  body={'kind':'applications','contents':'id,company,title,status,description\nqa1,Imported QA Care,Healthcare apprentice,applied,Assist residents\nbad,,Missing company,applied,Invalid\n'}
  for _ in range(2):assert post('/api/workspace/import',body)['imported']==1
  assert sum(a['company']=='Imported QA Care' for a in get('/api/applications'))==1
  c.get('/api/workspace/export/applications').raise_for_status()
  code=post('/api/workspace/recovery-code')['code']
  assert 'recovery_hash' not in str(get('/api/me/export'))
  if default_key:
   c.put('/api/workspace/key',json={'key':default_key}).raise_for_status()
   state=get('/api/workspace');assert state['key_configured'] and default_key not in str(state)
   assert default_key not in str(get('/api/me/export'))
   personal=post('/api/workspace/generate',{'application_id':app['id'],'kind':'follow_up'})
   assert not personal['fallback'] and 'apertus' in personal['model'].lower()
   c.delete('/api/workspace/key').raise_for_status()
   assert not get('/api/workspace')['key_configured']
  post('/api/auth/logout')
  post('/api/workspace/recover',{'username':username,'code':code,'new_password':'qa-new-strong-password'})
  assert c.post('/api/workspace/recover',json={'username':username,'code':code,'new_password':'qa-new-strong-password'}).status_code==401
  post('/api/auth/login',{'username':username,'password':'qa-new-strong-password'})
  c.delete('/api/me').raise_for_status()
  assert c.get('/api/me').status_code==401
 finally:
  c.delete("/api/me")

results.append({'registration':'pass','capture':'pass','imports':'pass','key':'pass' if default_key else 'skipped: set LLM_API_KEY','recovery':'pass','export':'pass','cleanup':'pass'})
Path(args.out).write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
