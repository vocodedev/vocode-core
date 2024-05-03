import logging
import httpx
from typing import Type
from pydantic import BaseModel, Field
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode.streaming.action.base_action import BaseAction
import json
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class GetTrainActionConfig(ActionConfig, type=ActionType.GET_TRAIN):
    starting_phrase: str


class GetTrainParameters(BaseModel):
    train_number: str = Field(
        ..., description="The train number to retrieve information for"
    )


class GetTrainResponse(BaseModel):
    train_number: str = Field(..., description="The train number that was queried")
    train_info: dict = Field(..., description="The information retrieved for the train")


class GetTrain(BaseAction[GetTrainActionConfig, GetTrainParameters, GetTrainResponse]):
    description: str = (
        "Retrieves information for a given train number from the Viaggiatreno service"
    )
    parameters_type: Type[GetTrainParameters] = GetTrainParameters
    response_type: Type[GetTrainResponse] = GetTrainResponse

    def extract_train_info(self, train_info_str: str):
        # Regex pattern to match the desired components
        pattern = r"(\d+)\s*-\s*(\w+(?:\s\w+)*)\|\1-([A-Z0-9]+)-(\d+)"

        # Search for matches
        match = re.match(pattern, train_info_str)

        # Check if a match is found and extract components
        if match:
            train_number, location, service_code_suffix, timestamp = match.groups()
            service_code = f"{train_number}-{service_code_suffix}"

            # Convert timestamp to more readable format
            timestamp_ms = int(timestamp)
            timestamp_s = timestamp_ms / 1000
            datetime_utc = datetime.fromtimestamp(
                timestamp_s, tz=timezone.utc
            ).isoformat()

            # Organize extracted information into a dictionary
            extracted_info = {
                "train_number": train_number,
                "location": location,
                "service_code": service_code,
                "timestamp": timestamp_ms,
                "datetime_utc": datetime_utc,
            }

            return extracted_info
        else:
            # Log an error if the input does not match the expected format
            logger.error(f"Unexpected format of train info: {train_info_str}")
            return {"error": "Unexpected format of train info"}

    async def get_train(self, train_number: str) -> dict:
        """
        Retrieves information for a given train number from the Viaggiatreno service.

        :param train_number: The train number to retrieve information for
        """
        url = f"http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/cercaNumeroTrenoTrenoAutocomplete/{train_number}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()

            # Use the new extraction method
            train_info = self.extract_train_info(response.text.strip())
            if train_info is None or "error" in train_info:
                return train_info or {"error": "Failed to extract train info"}

            return train_info

    async def run(
        self, action_input: ActionInput[GetTrainParameters]
    ) -> ActionOutput[GetTrainResponse]:
        train_number = action_input.params.train_number
        train_info = await self.get_train(train_number=train_number)

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=GetTrainResponse(train_number=train_number, train_info=train_info),
        )
