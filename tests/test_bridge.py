"""Exercise bridge authorization in isolation, without HA or audio playback."""
import ast
import re
import secrets
from pathlib import Path
from types import SimpleNamespace as NS
source=Path(__file__).parents[1]/'custom_components/interphone_live/__init__.py'
module=ast.parse(source.read_text())
bridge=next(n for n in module.body if isinstance(n,ast.ClassDef) and n.name=='Bridge')
entries={'media_player.allowed':NS(entity_id='media_player.allowed',domain='media_player',platform='music_assistant',disabled_by=None), 'media_player.other':NS(entity_id='media_player.other',domain='media_player',platform='other',disabled_by=None)}
ns={'er':NS(async_get=lambda hass:NS(async_get=entries.get)), 'secrets':secrets,'re':re}
exec(compile(ast.Module(body=[bridge],type_ignores=[]),str(source),'exec'),ns)
b=ns['Bridge'](NS(), {'speakers':['media_player.allowed']})
assert b.target()=='media_player.allowed'
for key in ['media_player.other','media_player.unlisted']:
 try:b.target(key)
 except ValueError:pass
 else:raise AssertionError('Unauthorized target accepted')
owner=object();token=secrets.token_urlsafe(32);b.session=NS(owner=owner,token=token)
assert b.owned(owner,token) is b.session
for connection,key in [(object(),token),(owner,'é'),(owner,'wrong')]:
 try:b.owned(connection,key)
 except ValueError:pass
 else:raise AssertionError('Unauthorized session accepted')
b.enabled=False
for action in [lambda:b.target(),lambda:b.owned(owner,token)]:
 try:action()
 except ValueError:pass
 else:raise AssertionError('Disabled bridge accepted command')
print('Bridge allowlist, ownership, malformed token and disabled-state checks passed')
