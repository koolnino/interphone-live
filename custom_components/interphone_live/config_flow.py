"""Single-instance setup and options flow."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector
from .settings import validate_settings

DOMAIN = 'interphone_live'

def eligible_entities(hass):
    return [e.entity_id for e in er.async_get(hass).entities.values()
            if e.domain == 'media_player' and e.platform == 'music_assistant' and not e.disabled_by]

def schema(hass, values):
    eligible = eligible_entities(hass)
    def entity(multiple=False):
        return selector.EntitySelector(selector.EntitySelectorConfig(
            domain='media_player', include_entities=eligible, multiple=multiple))
    return vol.Schema({
        vol.Required('speakers', default=values.get('speakers', [])): entity(True),
        vol.Optional('group', default=values.get('group', '')): str,
        vol.Optional('warmup_speakers', default=values.get('warmup_speakers', [])): entity(True),
        vol.Optional('warmup_seconds', default=values.get('warmup_seconds', 6)): vol.All(vol.Coerce(float), vol.Range(min=0, max=15)),
        vol.Optional('auto_resume', default=values.get('auto_resume', False)): bool,
        vol.Optional('audio_base_url', default=values.get('audio_base_url', '')): str,
    })

class InterphoneFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        errors = {}
        if user_input is not None:
            try:
                data = validate_settings(user_input, eligible_entities(self.hass))
                return self.async_create_entry(title='Interphone Live', data=data)
            except ValueError as error:
                errors['base'] = str(error)
        return self.async_show_form(step_id='user', data_schema=schema(self.hass, user_input or {}), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return InterphoneOptions()

class InterphoneOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        values = dict(self.config_entry.data) | dict(self.config_entry.options)
        errors = {}
        if user_input is not None:
            try:
                data = validate_settings(user_input, eligible_entities(self.hass))
                return self.async_create_entry(title='', data=data)
            except ValueError as error:
                errors['base'] = str(error)
                values = user_input
        return self.async_show_form(step_id='init', data_schema=schema(self.hass, values), errors=errors)
