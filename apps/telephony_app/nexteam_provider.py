import os
from typing import Optional

import requests
from loguru import logger

from vocode.streaming.models.telephony import BaseCallConfig
from vocode.streaming.telephony.config_manager.base_config_manager import BaseConfigManager
from vocode.streaming.utils.redis import initialize_redis


class NexteamConfigManager(BaseConfigManager):
    def __init__(self):
        self.redis = initialize_redis()

    async def _set_with_one_day_expiration(self, *args, **kwargs):
        ONE_DAY_SECONDS = 60 * 60 * 24
        return await self.redis.set(*args, **{**kwargs, "ex": ONE_DAY_SECONDS})

    async def save_config(self, conversation_id: str, config: BaseCallConfig):
        logger.debug(f"Saving config for {conversation_id} with NexteamProvider")

        raw_config = self.fetch_agent(conversation_id, config)
        if raw_config:
            parsed_config = BaseCallConfig.parse_raw(raw_config)
            await self._set_with_one_day_expiration(conversation_id, parsed_config.json())

    async def get_config(self, conversation_id) -> Optional[BaseCallConfig]:
        logger.debug(f"Getting config for {conversation_id} with NexteamProvider")
        raw_config = await self.redis.get(conversation_id)  # type: ignore
        if raw_config:
            return BaseCallConfig.parse_raw(raw_config)
        return None

    async def delete_config(self, conversation_id):
        logger.debug(f"Deleting config for {conversation_id}")
        # await self.redis.delete(conversation_id)

    def fetch_agent(self, call_id, config: BaseCallConfig):
        url = os.getenv("NEXTEAM_AGENT_WEBHOOK")
        try:
            payload = {
                "type": "event_request_agent",
                "call_id": call_id,
                "payload": {
                    "from_number": config.from_phone,
                    "to_number": config.to_phone,
                    "twilio_sid": config.twilio_sid,
                },
            }
            response = requests.get(url, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()
            data = response.text
            return data
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except requests.exceptions.ConnectionError as conn_err:
            print(f"Connection error occurred: {conn_err}")
        except requests.exceptions.Timeout as timeout_err:
            print(f"Timeout error occurred: {timeout_err}")
        except requests.exceptions.RequestException as req_err:
            print(f"An error occurred: {req_err}")
        except ValueError as json_err:
            print(f"JSON decoding failed: {json_err}")
