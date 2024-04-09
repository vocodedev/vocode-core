import logging
from vocode.streaming.models.agent import CommandAgentConfig
from vocode.streaming.models.actions import (
    ActionInput,
    FunctionCall,
    ActionType,
    FunctionFragment,
)

standard_tools = [
    {
        "name": "send_direct_response",
        "description": "Send the user a message directly, given the conversation history, must include the message",
        "parameter_definitions": {
            "message": {
                "description": "Message you intend to send to the user",
                "type": "str",
                "required": True,
            }
        },
    },
]

all_optional_tools = {
    ActionType.TRANSFER_CALL: {
        "name": "transfer_call",
        "description": "Transfers when the agent agrees to transfer the call",
        "parameter_definitions": {
            "transfer_reason": {
                "description": "The reason for transferring the call, limited to 120 characters",
                "type": "str",
                "required": True,
            }
        },
    },
    ActionType.HANGUP_CALL: {
        "name": "hangup_call",
        "description": "Hangup the call if the instructions are to do so",
        "parameter_definitions": {
            "end_reason": {
                "description": "The reason for ending the call, limited to 120 characters",
                "type": "str",
                "required": True,
            }
        },
    },
    ActionType.SEARCH_ONLINE: {
        "name": "search_online",
        "description": "Searches online when the agent says they will look something up",
        "parameter_definitions": {
            "query": {
                "description": "The search query to be sent to the online search API",
                "type": "str",
                "required": True,
            }
        },
    },
    ActionType.SEND_TEXT: {
        "name": "send_text",
        "description": "Triggered when the agent sends a text, only if they have been provided a valid phone number and a message to send.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the text message will be sent",
                "type": "str",
                "required": True,
            },
            "message": {
                "description": "The message to be sent, limited to 120 characters",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEND_HELLO_SUGAR_DIRECTIONS: {
        "name": "send_hello_sugar_directions",
        "description": "Triggered when the agent sends a text, only if they have been provided a valid phone number and a message to send.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the text message will be sent",
                "type": "str",
                "required": True,
            },
            "location": {
                "description": "The rough location the client would like directions for",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEND_HELLO_SUGAR_BOOKING_INSTRUCTIONS: {
        "name": "send_hello_sugar_booking_instructions",
        "description": "Triggered when the agent sends a text, only if they have been provided a valid phone number and a message to send.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the text message will be sent",
                "type": "str",
                "required": True,
            },
            "location": {
                "description": "The rough location the client would like directions for, including the city and state",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEND_EMAIL: None,
    ActionType.NYLAS_SEND_EMAIL: None,
    ActionType.GET_TRAIN: None,
    # {
    #     "name": "send_email",
    #     "description": "Triggered when the agent sends an email, only if they have been provided a valid recipient email, a subject, and a body for the email.",
    #     "parameter_definitions": {
    #         "recipient_email": {
    #             "description": "The email address of the recipient",
    #             "type": "str",
    #             "required": True,
    #         },
    #         "subject": {
    #             "description": "The subject of the email",
    #             "type": "str",
    #             "required": True,
    #         },
    #         "body": {
    #             "description": "The body of the email",
    #             "type": "str",
    #             "required": True,
    #         },
    #     },
    # },
    ActionType.USE_CALENDLY: {
        "name": "use_calendly",
        "description": "You can either list events or cancel an event. Listing events (list_events) also returns a booking link for scheduling tasks. You cannot schedule directly.",
        "parameter_definitions": {
            "api_key": {
                "description": "API key for Calendly",
                "type": "str",
                "required": True,
            },
            "action_type": {
                "description": "The type of Calendly action to perform",
                "type": "enum",
                "enum": ["list_events"],
                "required": True,
            },
            # "args": {
            #     "description": "Arguments required for the specific Calendly action. For cancel_event, include 'uuid' of the event and an optional 'reason'.",
            #     "type": "dict",
            #     "required": {"cancel_event": ["uuid"]},
            #     "optional": {"cancel_event": ["reason"]},
            # },
        },
    },
    ActionType.RETRIEVE_INSTRUCTIONS: {
        "name": "retrieve_instructions",
        "description": "Trigger when instructed to. Retrieves additional steps to follow. The numerical ID is required.",
        "parameter_definitions": {
            "id": {
                "description": "The ID of the instruction to retrieve",
                "type": "int",
                "required": True,
            },
        },
    },
}


def setup_command_r_tools(action_config: CommandAgentConfig, logger: logging.Logger):
    optional_tools = []

    if not action_config.actions:
        return standard_tools.copy()

    for action_config in action_config.actions:
        action_type: ActionType = action_config.type
        tool = all_optional_tools[action_type]
        if tool:
            optional_tools.append(tool)

    return optional_tools + standard_tools.copy()
