"""Mock-only tests: never connects to HA or starts real audio."""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
spec=importlib.util.spec_from_file_location('resume',Path(__file__).parents[1]/'custom_components/interphone_live/resume.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source='Spotify Connect (Example group)'
class Fake:
 def __init__(self,state='playing'):
  self.current=NS(state=state,attributes={'source':source,'source_list':[source],'media_content_id':'spotify_connect://audio_source/group','volume_level':.4})
  self.states=NS(get=lambda _:self.current);self.calls=[];self.services=NS(async_call=self.call)
 async def call(self,domain,action,data,blocking):
  self.calls.append((action,data))
  if action=='select_source':self.current.attributes['source']=data['source']
  if action=='media_play':self.current.state='playing'
async def run():
 h=Fake();r=m.SpotifyReturn(h,['group']);h.current.state='idle';h.current.attributes.update(source='Music Assistant Queue',media_content_id='https://ha/api/interphone_live/audio/test.wav');await r.restore()
 assert r.status=='resumed' and [x[0] for x in h.calls]==['select_source','media_play'] and h.current.attributes['volume_level']==.4
 await r.restore();assert len(h.calls)==2
 for state in ['idle','paused']:
  h=Fake(state);r=m.SpotifyReturn(h,['group']);await r.restore();assert not h.calls
 h=Fake();r=m.SpotifyReturn(h,['group']);h.current.attributes['media_content_id']='other://new-choice';await r.restore();assert r.status=='cancelled' and not h.calls
 h=Fake();r=m.SpotifyReturn(h,['group']);h.current.attributes['source_list']=[];h.current.state='idle';await r.restore();assert r.status=='failed' and not h.calls
 h=Fake();r=m.SpotifyReturn(h,['group']);r.started-=181;await r.restore();assert r.status=='cancelled' and not h.calls
 print('PASS: reprise source Spotify, volume intact, une seule reprise, silence/pauses respectés, nouvelle source et expiration protégées.')
asyncio.run(run())
