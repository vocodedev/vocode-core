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
        "name": "answer",
        "description": "Continue the conversation, given the conversation history. Always include the message.",
        "parameter_definitions": {
            "message": {
                "description": "Your direct response to the user",
                "type": "str",
                "required": True,
            }
        },
    },
]

all_optional_tools = {
    ActionType.CREATE_AGENT: {
        "name": "create_agent",
        "description": "Create a new agent with the specified attributes.",
        "parameter_definitions": {
            "name": {
                "description": "The name of the agent.",
                "type": "str",
                "required": True,
            },
            "gender": {
                "description": "The gender of the agent.",
                "type": "str",
                "required": True,
            },
            "job_title": {
                "description": "The job title of the agent.",
                "type": "str",
                "required": True,
            },
            "employer": {
                "description": "The employer of the agent.",
                "type": "str",
                "required": True,
            },
            "allow_interruptions": {
                "description": "Whether the agent allows interruptions.",
                "type": "bool",
                "required": True,
            },
            "agent_description": {
                "description": "A description of the agent.",
                "type": "str",
                "required": True,
            },
            "base_message": {
                "description": "The base message the agent will use.",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.TRANSFER_CALL: {
        "name": "transfer_call",
        "description": "Transfers when the agent agrees to transfer the call.",
        "parameter_definitions": {
            "phone_number_to_transfer_to": {
                "description": "The phone number to transfer the call to",
                "type": "str",
                "required": True,
            },
            "transfer_reason": {
                "description": "The reason for transferring the call, limited to 120 characters",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.HANGUP_CALL: {
        "name": "hangup_call",
        "description": "Hangup the call if the instructions are to do so.",
        "parameter_definitions": {
            "end_reason": {
                "description": "The reason for ending the call",
                "type": "str",
                "required": True,
            }
        },
    },
    ActionType.RETRIEVE_INSTRUCTIONS: {
        "name": "retrieve_instruction",
        "description": "Retrieve the instruction with the given ID.",
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
        "description": "Search online for the query provided.",
        "parameter_definitions": {
            "query": {
                "description": "The query to search for",
                "type": "str",
                "required": True,
            }
        },
    },
    ActionType.SEND_TEXT: {
        "name": "sms",
        "description": "Send an sms to the provided phone number.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the SMS will be sent",
                "type": "str",
                "required": True,
            },
            "contents": {
                "description": "The text to be sent",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEND_HELLO_SUGAR_DIRECTIONS: {
        "name": "send_hello_sugar_directions",
        "description": "Retrieve and send specialized directions to a particular phone number. Scheduled appointment is required to get directions.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the directions will be texted",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEND_HELLO_SUGAR_BOOKING_INSTRUCTIONS: {
        "name": "send_hello_sugar_booking_instructions",
        "description": "Sends a link to book an appointment at a specific Hello Sugar location. The location must be a city, landmark, or address.",
        "parameter_definitions": {
            "to_phone": {
                "description": "The phone number to which the instructions will be sent",
                "type": "str",
                "required": True,
            },
            "location": {
                "description": "The location to book an appointment at",
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
        "description": "Given a time and day, check the calendar.",
        "parameter_definitions": {
            "time": {
                "description": "The requested time to check availability, in the format HH:MM",
                "type": "str",
                "required": True,
            },
            "day": {
                "description": "The requested day, specified in natural language ('today', 'tomorrow', 'next thursday'), or in the format MM/DD/YYYY",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.BOOK_CALENDAR_APPOINTMENT: {
        "name": "book_calendar_appointment",
        "description": "Book an appointment for the client on the calendar.",
        "parameter_definitions": {
            "details": {
                "description": "The reason for the appointment",
                "type": "str",
                "required": True,
            },
            "date": {
                "description": "The appointment date",
                "type": "str",
                "required": True,
            },
            "time": {
                "description": "The appointment starting time",
                "type": "str",
                "required": True,
            },
            "guest_email": {
                "description": "The email of the person requesting the appointment",
                "type": "str",
                "required": True,
            },
            "guest_name": {
                "description": "The name of the person requesting the appointment",
                "type": "str",
                "required": True,
            },
        },
    },
    ActionType.SEARCH_DOCUMENTS: {
        "name": "search_documents",
        "description": "Get an answer to a question by asking the document system provided to the agent. Must include a query.",
        "parameter_definitions": {
            "query": {
                "description": "A natural language query for the document system to answer",
                "type": "str",
                "required": True,
            },
        },
    },
    # Design decision: name value and ActionType are different because in the future, we will
    # want many different customer support queues.
    # We will preserve the name of the function since we know it will be consistently called
    # but the underlying implementation of the function call will change
    ActionType.FORWARD_CALL_TO_MOOVS: {
        "name": "get_human_support",
        "description": "Puts a human support agent into the call.",
        "parameter_definitions": {},
    }
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
