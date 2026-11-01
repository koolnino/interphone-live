"""One-shot restoration of an interrupted Spotify Connect source."""
import time
import asyncio

class SpotifyReturn:
    def __init__(self, hass, entities):
        self.hass = hass
        self.items = []
        self.started = time.monotonic()
        self.status = 'not_needed'
        self.message = 'Aucune lecture Spotify en cours à reprendre.'
        for entity in dict.fromkeys(entities):
            state = hass.states.get(entity)
            if not state or state.state != 'playing':
                continue
            attrs = state.attributes
            source = attrs.get('source', '')
            content = attrs.get('media_content_id', '')
            if (isinstance(source, str) and isinstance(content, str)
                    and content.startswith('spotify_connect://')
                    and source in attrs.get('source_list', [])):
                self.items.append((entity, source, content))
                break
        if self.items:
            self.status = 'pending'
            self.message = 'Retour à Spotify prévu après le direct.'

    def info(self):
        return {'status': self.status, 'message': self.message}

    async def restore(self):
        if self.status not in ('pending', 'failed'):
            return
        if time.monotonic() - self.started > 180:
            self.status, self.message = 'cancelled', 'Retour expiré : relance Spotify sur l’iPhone.'
            return
        self.status = 'restoring'
        try:
            for entity, source, content in self.items:
                state = self.hass.states.get(entity)
                if not state or state.state in ('unavailable', 'unknown'):
                    raise ValueError('Lecteur indisponible')
                attrs = state.attributes
                current = attrs.get('media_content_id', '') or ''
                # Never overwrite a new song/source chosen while the intercom was active.
                if (current and current != content
                        and '/api/interphone_live/audio/' not in current):
                    self.status, self.message = 'cancelled', 'Nouvelle lecture détectée : reprise automatique annulée.'
                    return
                if state.state == 'playing' and attrs.get('source') == source:
                    continue
                if source not in attrs.get('source_list', []):
                    raise ValueError('Source Spotify indisponible')
                await self.hass.services.async_call('media_player', 'select_source',
                    {'entity_id': entity, 'source': source}, blocking=True)
                await self.hass.services.async_call('media_player', 'media_play',
                    {'entity_id': entity}, blocking=True)
            for _ in range(8):
                state = self.hass.states.get(self.items[0][0])
                if state and state.state == 'playing' and state.attributes.get('source') == self.items[0][1]:
                    self.status, self.message = 'resumed', 'Lecture Spotify reprise.'
                    return
                await asyncio.sleep(.5)
            self.status, self.message = 'failed', 'Reprise demandée mais non confirmée. Utilise « Revenir à Spotify » ou Spotify sur l’iPhone.'
        except Exception:
            self.status, self.message = 'failed', 'Reprise Spotify non aboutie. Utilise « Revenir à Spotify » ou l’application Spotify.'
