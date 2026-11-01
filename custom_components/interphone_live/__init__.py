"""Authenticated push-to-talk prototype for a Music Assistant speaker."""
import asyncio
import base64
import binascii
import logging
import secrets
import re
import time
from pathlib import Path

import voluptuous as vol
from aiohttp import web
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.network import get_url
from .audio import AudioSession, MAX_SECONDS, wav_header
from .resume import SpotifyReturn

DOMAIN = 'interphone_live'
LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

class Bridge:
    def __init__(self, hass, options):
        self.hass, self.options = hass, options
        self.enabled = True
        self.session = None
        self.last_status = {}
        self.tasks = set()
        self.spotify_return = None
        self.return_owner = None

    def spawn(self, coro):
        task = self.hass.async_create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def target(self, key=None):
        key = key or self.options['speakers'][0]
        allowed = self.options['speakers'] + ([self.options['group']] if self.options.get('group') else [])
        if key not in allowed:
            raise ValueError('Destination non autorisée')
        entry = er.async_get(self.hass).async_get(key)
        if (not self.enabled or not entry or entry.disabled_by
                or entry.domain != 'media_player' or entry.platform != 'music_assistant'):
            raise ValueError('Destination Music Assistant indisponible')
        return entry.entity_id

    def destinations(self):
        result = []
        ids = list(self.options['speakers'])
        if self.options.get('group'):
            ids.append(self.options['group'])
        for entity in ids:
            state = self.hass.states.get(entity)
            try:
                self.target(entity)
                available = bool(state and state.state not in ('unavailable', 'unknown'))
            except ValueError:
                available = False
            result.append({'id': entity, 'name': state.name if state else entity,
                           'available': available, 'entity_id': entity})
        return result

    def owned(self, connection, token):
        s = self.session
        if (not self.enabled or not s or s.owner is not connection
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token)
                or not secrets.compare_digest(s.token, token)):
            raise ValueError('Session absente ou non autorisée')
        return s

    def status(self, s=None):
        if s is None:
            s = self.session
        if s is None:
            return self.last_status
        return {'active': not s.ended, 'bytes': s.bytes_received,
                'playback_requested': s.playback_requested,
                'audio_readers': s.max_readers, 'error': s.error,
                'seconds': round(time.monotonic() - s.started, 1),
                'spotify_return': self.spotify_return.info() if self.spotify_return else None}

    async def launch(self, s):
        try:
            # Wait for PCM before asking MA to probe the URL.
            while not s.ended and s.bytes_received < 8000:
                await asyncio.sleep(.05)
                if time.monotonic() - s.started > 3:
                    raise ValueError('Aucun audio reçu du microphone')
            if s.ended:
                return
            url = self.options.get('audio_base_url') or get_url(self.hass, prefer_external=False)
            audio_url = f'{url}/api/interphone_live/audio/{s.token}.wav'
            s.playback_requested = True
            await self.hass.services.async_call('music_assistant', 'play_media', {
                'entity_id': s.target, 'media_id': audio_url,
                'media_type': 'radio', 'enqueue': 'replace',
            }, blocking=True)
        except Exception:
            s.error = 'Music Assistant ne peut pas ouvrir le flux. Voir les journaux.'
            LOGGER.warning('Interphone: échec de la demande de lecture', exc_info=False)
            await s.finish()

    async def watch(self, s):
        while not s.ended:
            await asyncio.sleep(.5)
            now = time.monotonic()
            if now - s.started >= MAX_SECONDS or now - s.last_audio > 3:
                await s.finish()
        self.last_status = self.status(s)
        # Let the voice HTTP consumer finish before handing the source back.
        await asyncio.sleep(2)
        for _ in range(16):
            if not s.readers:
                break
            await asyncio.sleep(.5)
        if self.session is s and s.playback_requested and getattr(s, 'spotify_return', None):
            await s.spotify_return.restore()
        elif getattr(s, 'spotify_return', None) and s.spotify_return.status == 'pending':
            s.spotify_return.status = 'cancelled'
            s.spotify_return.message = 'Aucun flux lancé : aucune reprise demandée.'
        await asyncio.sleep(3)
        if self.session is s:
            self.last_status = self.status(s)
            self.session = None

    async def start(self, connection, test=False, destination=None):
        if not self.enabled:
            raise ValueError('Interphone non configuré')
        if self.session is not None:
            if not self.session.ended:
                raise ValueError('Une transmission est déjà en cours')
            if self.session.readers or (self.spotify_return and self.spotify_return.status in ('pending', 'restoring')):
                raise ValueError('Le flux précédent se termine. Réessayer dans quelques secondes.')
        target = self.target(destination)
        state = self.hass.states.get(target)
        if not state or state.state in ('unavailable', 'unknown'):
            raise ValueError('La destination sélectionnée est indisponible')
        if not self.hass.services.has_service('music_assistant', 'play_media'):
            raise ValueError('Action Music Assistant absente')
        s = self.session = AudioSession(connection, target, secrets.token_urlsafe(32))
        # Resume only the selected destination, never guess a different active group.
        self.spotify_return = SpotifyReturn(self.hass, [target]) if self.options.get('auto_resume', False) and not test else None
        self.return_owner = connection.user.id
        s.spotify_return = self.spotify_return
        self.spawn(self.launch(s))
        self.spawn(self.watch(s))
        if test:
            self.spawn(self.silence(s))
        return s

    async def silence(self, s):
        try:
            for _ in range(100):
                if s.ended:
                    break
                await s.append(bytes(2560))
                await asyncio.sleep(.08)
        finally:
            await s.finish()

class AudioView(HomeAssistantView):
    url = '/api/interphone_live/audio/{token}.wav'
    name = 'api:interphone_live:audio'
    requires_auth = False
    def __init__(self, bridge):
        self.bridge = bridge
    async def get(self, request, token):
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            raise web.HTTPNotFound()
        s = self.bridge.session
        if (not self.bridge.enabled or not s or not secrets.compare_digest(token, s.token)
                or time.monotonic() - s.started > MAX_SECONDS + 5):
            raise web.HTTPNotFound()
        if s.readers >= 3:
            raise web.HTTPTooManyRequests()
        response = web.StreamResponse(headers={
            'Content-Type': 'audio/wav', 'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'Accept-Ranges': 'none',
        })
        s.readers += 1
        s.max_readers = max(s.max_readers, s.readers)
        try:
            await response.prepare(request)
            await response.write(wav_header())
            async for chunk in s.chunks():
                await response.write(chunk)
            await response.write_eof()
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            s.readers -= 1
        return response

@websocket_api.websocket_command({vol.Required('type'): 'interphone_live/info'})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_info(hass, connection, msg):
    bridge = hass.data[DOMAIN]
    try:
        target = bridge.target()
        state = hass.states.get(target)
        connection.send_result(msg['id'], {'target': target,
            'name': state.name if state else target, 'status': bridge.status(),
            'destinations': bridge.destinations(), 'default_destination': bridge.options['speakers'][0],
            'group_destination': bridge.options.get('group'),
            'warmup_destinations': bridge.options.get('warmup_speakers', []),
            'warmup_seconds': bridge.options.get('warmup_seconds', 6),
            'auto_resume': bridge.options.get('auto_resume', False),
            'spotify_return': bridge.spotify_return.info() if bridge.spotify_return else None})
    except ValueError as error:
        connection.send_error(msg['id'], 'target', str(error))

@websocket_api.websocket_command({vol.Required('type'): 'interphone_live/start',
                                vol.Optional('test', default=False): bool,
                                vol.Optional('destination'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_start(hass, connection, msg):
    try:
        s = await hass.data[DOMAIN].start(connection, msg['test'], msg.get('destination'))
        connection.send_result(msg['id'], {'session': s.token, 'max_seconds': MAX_SECONDS})
    except ValueError as error:
        connection.send_error(msg['id'], 'start', str(error))

@websocket_api.websocket_command({vol.Required('type'): 'interphone_live/audio',
    vol.Required('session'): str, vol.Required('sequence'): vol.All(int, vol.Range(min=0)),
    vol.Required('pcm'): vol.All(str, vol.Length(max=5500))})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_audio(hass, connection, msg):
    try:
        s = hass.data[DOMAIN].owned(connection, msg['session'])
        if msg['sequence'] != s.sequence:
            raise ValueError('Séquence audio interrompue')
        data = base64.b64decode(msg['pcm'], validate=True)
        # Bounded memory and upload: at most 1 s of data ahead of real time.
        if s.bytes_received + len(data) > (time.monotonic() - s.started + 1) * 32000:
            raise ValueError('Débit audio excessif')
        await s.append(data)
        s.sequence += 1
        connection.send_result(msg['id'], None)
    except (ValueError, binascii.Error) as error:
        connection.send_error(msg['id'], 'audio', str(error))

@websocket_api.websocket_command({vol.Required('type'): 'interphone_live/stop',
                                vol.Required('session'): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_stop(hass, connection, msg):
    try:
        s = hass.data[DOMAIN].owned(connection, msg['session'])
        await s.finish()
        connection.send_result(msg['id'], hass.data[DOMAIN].status(s))
    except ValueError as error:
        connection.send_error(msg['id'], 'stop', str(error))

@websocket_api.websocket_command({vol.Required('type'): 'interphone_live/resume'})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_resume(hass, connection, msg):
    bridge = hass.data[DOMAIN]
    if (bridge.return_owner != connection.user.id or not bridge.spotify_return):
        connection.send_error(msg['id'], 'resume', 'Aucune lecture Spotify interrompue à reprendre')
        return
    if bridge.session and (not bridge.session.ended or bridge.session.readers):
        connection.send_error(msg['id'], 'resume', 'Le direct vocal se termine encore')
        return
    await bridge.spotify_return.restore()
    connection.send_result(msg['id'], bridge.spotify_return.info())

async def async_setup_entry(hass, entry):
    """Register transport once; apply options without touching the private prototype."""
    options = dict(entry.data) | dict(entry.options)
    bridge = hass.data.get(DOMAIN)
    if bridge is None:
        bridge = hass.data[DOMAIN] = Bridge(hass, options)
        hass.http.register_view(AudioView(bridge))
        await hass.http.async_register_static_paths([StaticPathConfig(
            '/interphone_live/panel.js', str(Path(__file__).parent / 'panel.js'), False)])
        for command in (ws_info, ws_start, ws_audio, ws_stop, ws_resume):
            websocket_api.async_register_command(hass, command)
        async def shutdown(_event):
            await close_bridge(bridge)
        hass.bus.async_listen_once('homeassistant_stop', shutdown)
    else:
        bridge.options, bridge.enabled = options, True
    await panel_custom.async_register_panel(hass,
        webcomponent_name='interphone-live-panel', frontend_url_path='interphone-live',
        sidebar_title='Interphone Live', sidebar_icon='mdi:microphone-message',
        module_url='/interphone_live/panel.js?v=0.1.0-beta.1',
        embed_iframe=False, require_admin=True)
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True

async def close_bridge(bridge):
    bridge.enabled = False
    if bridge.session:
        await bridge.session.finish()
    tasks = list(bridge.tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    bridge.tasks.clear()
    bridge.session = None
    bridge.spotify_return = None
    bridge.return_owner = None
    bridge.last_status = {}

async def async_unload_entry(hass, entry):
    await close_bridge(hass.data[DOMAIN])
    frontend.async_remove_panel(hass, 'interphone-live')
    return True

async def async_options_updated(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)
