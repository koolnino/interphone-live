"""Pure settings validation: no Home Assistant and no network."""
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location('settings', Path(__file__).parents[1]/'custom_components/interphone_live/settings.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
allowed = ['media_player.speaker', 'media_player.group']
base = {'speakers': [allowed[0]], 'group': allowed[1]}
assert m.validate_settings(base, allowed)['audio_base_url'] == ''
assert m.validate_settings(base | {'audio_base_url': 'https://example.invalid:8123/'}, allowed)['audio_base_url'] == 'https://example.invalid:8123'
for extra in [{'speakers': []}, {'speakers': ['media_player.other']}, {'group': allowed[0]}, {'warmup_speakers': ['media_player.other']}, {'warmup_seconds': -1}, {'warmup_seconds': 16}, {'audio_base_url': 'https://user:pass@example.invalid'}, {'audio_base_url': 'https://example.invalid/path'}, {'audio_base_url': 'javascript:alert(1)'}, {'audio_base_url': 'https://example.invalid?token=secret'}]:
    try:
        m.validate_settings(base | extra, allowed)
    except ValueError:
        pass
    else:
        raise AssertionError(extra)
print('Settings validation passed')
