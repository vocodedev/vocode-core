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
        "description": "Continue the conversation, given the conversation history. Must include the message.",
        "parameter_definitions": {
            "message": {
                "description": "Your reply to the user.",
                "type": "str",
                "required": True,
            }
        },
    },
]

all_optional_tools = {
    ActionType.TRANSFER_CALL: {
        "name": "transfer_call",
        "description": "Transfers when the agent agrees to transfer the call.",
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
        "description": "Hangup the call if the instructions are to do so.",
        "parameter_definitions": {
            "end_reason": {
                "description": "The reason for ending the call, limited to 120 characters",
                "type": "str",
                "required": True,
            }
        },
    },
    ActionType.RETRIEVE_INSTRUCTIONS: {
        "name": "retrieve_instruction",
        "description": "Certain steps specify an instruction id to retrieve before moving on. This action retrieves the instruction.",
        "parameter_definitions": {
            "id": {
                "description": "The ID number of the instruction to retrieve",
                "type": "int",
                "required": True,
            },
        },
    },
    ActionType.SEARCH_ONLINE: {
        "name": "search_online",
        "description": "Searches online when the agent says they will look something up.",
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
        "description": "Send an sms to a phone number.",
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
        "description": "Sends a text with directions to the caller given a specific location and the number they're calling from.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the directions will be texted",
                "type": "str",
                "required": True,
            },
            "location": {
                "description": "The rough location the client is trying to get to, including the city and state",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEND_HELLO_SUGAR_BOOKING_INSTRUCTIONS: {
        "name": "send_hello_sugar_booking_instructions",
        "description": "Sends instructions on how to actually book an appointment at a specific Hello Sugar location.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the instructions will be sent",
                "type": "str",
                "required": True,
            },
            "location": {
                "description": "The rough appointment location",
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
        "description": "Listing events (list_events) also returns a booking link for scheduling tasks. You cannot schedule directly.",
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
    ActionType.CHECK_CALENDAR_AVAILABILITY: {
        "name": "check_calendar_availability",
        "description": "Check calendar availability for the client's appointment",
        "parameter_definitions": {
            "day": {
                "description": "the day or date that the client would like to book an appointment",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.BOOK_CALENDAR_APPOINTMENT: {
        "name": "book_calendar_appointment",
        "description": "Book an appointment for the client on the calendar",
        "parameter_definitions": {
            "date": {
                "description": "the date and time for the appointment",
                "type": "str",
                "required": True,
            },
            "guest_email": {
                "description": "email of the person who is requesting this appointment",
                "type": "str",
                "required": True,
            },
            "guest_name": {
                "description": "name of the person who is requesting this appointment",
                "type": "str",
                "required": True,
            },
            "description": {
                "description": "summary of the appointment reason",
                "type": "str",
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
