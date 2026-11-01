"""Pure configuration validation, without network calls."""
from urllib.parse import urlsplit

def validate_settings(data, eligible):
    result = dict(data)
    speakers = list(dict.fromkeys(result.get('speakers', [])))
    group = result.get('group', '')
    if not speakers or any(x not in eligible for x in speakers):
        raise ValueError('invalid_speakers')
    if group and (group not in eligible or group in speakers):
        raise ValueError('invalid_group')
    allowed = speakers + ([group] if group else [])
    if any(x not in allowed for x in result.get('warmup_speakers', [])):
        raise ValueError('invalid_warmup')
    seconds = result.get('warmup_seconds', 6)
    if isinstance(seconds, bool) or not isinstance(seconds, (float, int)) or not 0 <= seconds <= 15:
        raise ValueError('invalid_warmup')
    url = result.get('audio_base_url', '').strip().rstrip('/')
    if url:
        try:
            parts = urlsplit(url)
            valid = parts.scheme in ('http', 'https') and parts.hostname and not (parts.username or parts.password or parts.query or parts.fragment or parts.path)
            _ = parts.port
        except ValueError:
            valid = False
        if not valid:
            raise ValueError('invalid_url')
    result.update(speakers=speakers, group=group, audio_base_url=url)
    return result
