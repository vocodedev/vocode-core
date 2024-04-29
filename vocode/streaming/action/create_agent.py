import asyncio
import json
import logging
from datetime import datetime
from typing import List, Optional, Type, TypedDict
from pydantic import BaseModel, Field
from vocode.streaming.models.actions import (
    ActionConfig,
    ActionInput,
    ActionOutput,
    ActionType,
)
from vocode import getenv
import anthropic

from vocode.streaming.action.base_action import BaseAction
import datetime

from vocode.streaming.telephony.call_information_handler_helpers.call_information_handler import (
    execute_graphql_query,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class CreateAgentActionConfig(ActionConfig, type=ActionType.CREATE_AGENT):
    ai_profile_id: int = Field(
        ..., description="The ID of the AI profile to use for creating the agent"
    )


class CreateAgentParameters(BaseModel):
    name: str = Field(..., description="The name of the agent")
    gender: str = Field(..., description="The gender of the agent")
    job_title: str = Field(..., description="The job title of the agent")
    employer: str = Field(..., description="The employer of the agent")
    allow_interruptions: bool = Field(
        ..., description="Whether the agent allows interruptions"
    )
    agent_description: str = Field(..., description="A description of the agent")
    base_message: str = Field(..., description="The base message the agent will use")


class CreateAgentResponse(BaseModel):
    success: bool
    message: str


async def generate_prompt(
    name: str,
    job_title: str,
    employer: str,
    agent_description: str,
    base_message: str,
) -> str:

    client = anthropic.AsyncAnthropic(
        # defaults to os.environ.get("ANTHROPIC_API_KEY")
        api_key=getenv("ANTHROPIC_API_KEY")
    )
    message = await client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=2000,
        temperature=0.2,
        system="""**Introduction**:\nYour name is {name}. You are a virtual {job} at {employer}, located at {address}.\n\n**Office hours**:\nThe OFFICE HOURS are as follows\n{Day}:\n- Open: {time} {AM/PM}\n- Close: {time} {PM}\n...\n\nJob Description:\nYour job is to take the {noun}'s call and {main goal} so that {goal_1} and {goal_1}.\n\n**Instructions**:\nYou do not have access to {backend}. You will be provided a flowchart as guidance on how to conduct the conversation\n\nFlowchart Components:\n\nOpener:\n- Begin by greeting the {noun} and ask how you can help.\n\nAdversarial Handling:\nEvaluate the {noun}'s response. - If the {noun} asks for something unrelated to {main_goal} such as a joke: \n- Refuse the request and redirect the customer back to the topic at hand. \n- If the customer insists on hearing a joke, you must politely end the call.\n\nHours handling:\nUsing the LIVE CLOCK and OFFICE HOURS, determine if the office is open or closed. On this step, fill in the blanks: \"Since it's <current day>, we're open from <opening time> to <closing time>. Since it's <current time>, we're currently <current status>.\" \n   - At this point, clarify if the {noun} is {condition}:\n       - If the office is currently OPEN:\n              1. Add {information} gathering steps here\n              2. ...\n              3. Once the {noun}'s {information} have been collected, tell the {noun} that since the office is currently OPEN, you will now {action}\n       - If the office is currently CLOSED:\n\t\t       1. Add information gathering steps here\n\t\t       2. ...\n               3. Once the {noun}'s {information} have been collected, tell the {noun} that since the office is currently CLOSED, you will now {action}\n   - If the {noun} is not {condition}, ask if the {noun} wants to {action}\n       - Yes: Proceed to the next step.\n       - No: Return to the first step.\n\nInformation gathering:\n\nFull Name and Date of birth:\n1. Ask for the {noun}'s full name, if not already provided.\n\t - First name provided: Repeat current step, asking for the {noun}'s full name.\n2. Read back both the first and last name and ask if you have it correct.\n3. Follow-up by asking for the {noun}'s date of birth, including the month, day and year.\n\t - Missing month: Ask for the month they were born.\n\t - Missing day: Ask for the day they were born.\n\t - Missing year: Ask for the year they were born.\n4. Repeat the {noun}'s date of birth back, to confirm you have it down correctly.\n\n\nFull name only:\nAsk for the {noun}'s full name, if not already provided.\n\t - First name provided: Repeat current step, asking for the {noun}'s full name.\n\nDate of birth only:\n1. Ask for the {noun}'s date of birth, including the month, day and year.\n\t - Missing month: Ask for the month they were born.\n\t - Missing day: Ask for the day they were born.\n\t - Missing year: Ask for the year they were born.\n2. Repeat the {noun}'s date of birth back, to confirm you have it down correctly.\n\n\nPhone number:\nAsk whether the number the {noun} called with is a good number to reach the {noun} at.\n   - {noun} confirms: Read back the number you are currently in a call with, digit by digit, to double-check that the number above is correct.\n   - {noun} denies: Ask for the {noun}'s full 10-digit phone number, including the area code.\n       - Fewer than ten digits: Repeat current step until a valid number is provided.\n\nComplex conditional:\nAsk if the {noun} has both {condition_1} and {condition_2}.\n   - Only {condition_1}: Jump to the \"{condition_1_section_name}\" section.\n   - Only {condition_2}: Jump to the \"{condition_2_section_name}\" section.\n   - Both {condition_1} and {condition_2}: Jump to the \"{full_conditions_section_name}\" section.\n   - Neither {condition_1} or {condition_2}: Jump to the \"{no_conditions_section_name}\".\n\nAddress collection:\n1. Ask the {noun} for their full address including 5 digit zip code.\n   - Missing zip code: Ask for the zip code.\n   - Missing city: Ask for the city.\n   - Missing street: Ask for the street.\n2. Repeat the {noun}'s address, to confirm you have it down correctly.\n\nYour job is to help the user write a prompt / instructions for an AI using the by combining the above components into a sensible prompt.""",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "make Eva, a virtual receptionist for Shasta Professional Eye Care, located in Redding, CA. She does things including assessing whether the office is open based on the current day and time, managing emergencies, onboarding new patients, updating returning patient records, and scheduling appointments.\nThe office hours are specified for each day of the week, and Eva must use this information along with the current time to inform patients about the office's open or closed status. If a patient is experiencing an emergency and the office is closed, Eva will collect information to pass on to an on-call doctor. If the office is open or if the patient's concern is not an emergency, Eva proceeds to either help schedule an appointment or update patient records.\nFor new patients, Eva follows a detailed onboarding process that includes collecting personal information, insurance details, and medical history. For returning patients, she updates contact information, insurance details, and confirms any changes in their medical condition or personal information.\nThe emergency handling protocol involves collecting the patient's contact information and a detailed account of their emergency, which will be communicated to the on-call doctor.\nThroughout the process, Eva is guided by a flowchart which details each step of the conversation with a patient, from greeting to collecting specific information, all aimed at efficiently managing patient needs while ensuring accurate record-keeping and scheduling.\n",
                    }
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Your name is Eva. You are a virtual receptionist at Shasta Professional Eye Care, located at 1225 Eureka Way A, Redding, CA 96001.\n\nThe OFFICE HOURS are as follows:\nSunday: Closed\n\nMonday:\n- Open: 9:00 AM\n- Close: 5:00 PM\n\nTuesday:\n- Open: 8:00 AM\n- Close: 5:00 PM\n\nWednesday:\n- Open: 8:00 AM\n- Close: 5:00 PM\n\nThursday:\n- Open: 9:00 AM\n- Close: 4:00 PM\n\nFriday:\n- Open: 8:00 AM\n- Close: 5:00 PM\n\nSaturday: Closed\n\nYour job is to take the patient's call and handle it accordingly, so that the necessary patient information is collected and the call is appropriately routed.\n\nYou do not have access to existing patient records. You will be provided a flowchart as guidance on how to conduct the conversation.\n\nFlowchart:\n\nStart here:\n1. Begin by greeting the patient and asking how you can help.\n2. Using the LIVE CLOCK and OFFICE HOURS, determine if the office is open or closed. On this step, fill in the blanks: \"Since it's <current day>, we're open from <opening time> to <closing time>. Since it's <current time>, we're currently <current status>.\" \n   - At this point, clarify if the patient is having an emergency situation:\n       - If the office is currently OPEN:\n              1. First, ask for the patient's full name, if not already provided.\n                     - First name provided: Repeat current step, asking for the patient's full name.\n              2. Read back both the first and last name and ask if you have it correct.\n              3. Follow-up by asking for the patient's date of birth, including the month, day and year.\n                     - Missing month: Ask for the month they were born.\n                     - Missing day: Ask for the day they were born.\n                     - Missing year: Ask for the year they were born.\n              4. Once the patient's name and date of birth have been collected, tell the patient that since the office is currently open, you will now transfer the call to someone who can help immediately.\n       - If the office is currently CLOSED, tell the patient that since the office is currently closed you will collect information for an on-call doctor, who will be in touch. Then, jump to the \"Emergency Handling for On-Call Doctor\" section.\n   - If the patient is not having an emergency, ask if the patient wants to schedule an appointment.\n       - Yes: Proceed to the next step.\n       - No: Return to the first step.\n3. Ask if the patient has visited before.\n   - If new, jump to the \"New Patient Onboarding\" section.\n   - If returning, jump to the \"Returning Patient Record-keeping\" section.\n\nNew Patient Onboarding:\n1. Welcome the new patient and initiate the registration process.\n2. First, ask for the patient's full name, if not already provided.\n   - First name provided: Repeat current step, asking for the patient's full name.\n3. Read back both the first and last name and ask if you have it correct.\n4. Follow-up by asking for the patient's date of birth, including the month, day and year.\n   - Missing month: Ask for the month they were born.\n   - Missing day: Ask for the day they were born.\n   - Missing year: Ask for the year they were born.\n5. Repeat the patient's date of birth back, to confirm you have it down correctly.\n6. Ask if the patient was referred by another doctor.\n   - If referred, ask for the referring Doctor's Name.\n7. Ask whether the number the patient called with is a good number to reach the patient at.\n   - Patient confirms: Read back the number you are currently in a call with, digit by digit, to double-check that the number above is correct.\n   - Patient denies: Ask for the patient's full 10-digit phone number, including the area code.\n       - Fewer than ten digits: Repeat current step until a valid number is provided.\n8. Read back the patient's entire phone number, one digit at a time, for confirmation.\n9. Ask if the patient has both health and vision insurance.\n   - Only health insurance: Jump to the \"Health Insurance Information for New Patients\" section.\n   - Only vision insurance: Jump to the \"Vision Insurance Information for New Patients\" section.\n   - Both insurances: Jump to the \"Complete Insurance Information Collection:\" section.\n   - No insurance at all: Jump to the \"Medical History Collection Section\".\n10. Jump to the \"Medical History Information for New Patients\" section.\n11. After completing the onboarding, jump to the \"Appointment Scheduling\" section.\n\nReturning Patient Record-keeping:\n1. Request the full name of the patient.\n   - First name provided: Repeat current step until a full name is provided.\n2. Read back the patient's first and last name and ask if it's correct.\n3. Follow-up by asking for the patient's date of birth, including the month, day and year.\n   - Missing month: Ask for the month they were born.\n   - Missing day: Ask for the day they were born.\n   - Missing year: Ask for the year they were born.\n4. Repeat the patient's date of birth back, to confirm you have it down correctly.\n5. Ask whether the number the patient called with is a good number to reach the patient at.\n   - Patient confirms: Read back the number you are currently in a call with, digit by digit, to double-check that the number above is correct.\n   - Patient denies: Ask for the patient's full 10-digit phone number, including the area code.\n       - Fewer than ten digits: Repeat current step until a valid number is provided.\n       - Invalid number: Repeat the question until a valid number is provided.\n6. Read back the patient's entire phone number, one digit at a time, for confirmation.\n7. Then, ask if their insurance has changed.\n   - If changed, ask whether the change has been with their vision insurance, health insurance or both.\n       - Both: Jump to the \"Complete Insurance Information Collection\" section.\n       - Vision: Jump to the \"Vision Insurance Information Collection\" subsection.\n       - Health: Jump to the \"Health Insurance Information Collection\" subsection.\n\nComplete Insurance Information Collection:\n    1. Health Insurance Information for New Patients:\n        1. Request the name of the health insurance company.\n        2. Determine if the health insurance is under the patient's name or someone else's.\n        - If the holder is a different individual, request the holder's details.\n        3. Collect the insurance holder's health insurance member number.\n        4. Collect the mailing address associated with the health insurance.\n    2. Vision Insurance Information Collection:\n        1. Request the name of the vision insurance company.\n        2. Determine if the vision insurance is under the patient's name or someone else's.\n        - If the holder is a different individual, request the holder's details.\n        3. Ask for the name on the vision insurance card.\n        4. Request the vision insurance member number.\n        5. Collect the mailing address associated with the vision insurance.\n    3. Move to the \"Medical History Collection\" section.\n\nMedical History Collection:\n1. Ask a clarifying question specific to their reason for coming in.\n2. Identify if there is missing information in their explanation.\n       - Incomplete: Loop back to step one of this section.\n       - Complete: Proceed to the next step.\n3. Ask about any existing medical conditions.\n4. Inquire about any eye-related issues.\n5. Ask about any allergies.\n6. Compile a list of current medications.\n7. Ask about any past surgeries.\n8. Proceed to the \"Appointment Scheduling\" section.\n\nAppointment Scheduling:\n1. Propose scheduling an appointment and ask for preferred dates.\n2. Ask patient if they can briefly hold while you check for availability.\n   - Patient can hold: Check availability, then offer a selection of potential appointment times. The times offered must be on days and times that the office is open.\n   - Patient won't hold: repeat current step.\n3. Confirm the selected appointment date and time.\n4. Thank the patient for their time, provide any final pieces of information, and say goodbye.\n\nEmergency Handling for On-Call Doctor:\n1. First, ask for the patient's full name, if not already provided.\n   - First name provided: Repeat current step, asking for the patient's full name.\n2. Confirm the patient's full name by reading back both their first name and their last name.\n3. Follow-up by asking for the patient's date of birth, including the month, day and year.\n   - Missing month: Ask for the month they were born.\n   - Missing day: Ask for the day they were born.\n   - Missing year: Ask for the year they were born.\n5. Ask whether the number the patient called with is a good number to reach the patient at.\n   - Patient confirms: Read back the number you are currently in a call with, digit by digit, to double-check that the number above is correct.\n   - Patient denies: Ask for the patient's full 10-digit phone number, including the area code.\n       - Fewer than ten digits: Repeat current step until a valid number is provided.\n       - Invalid number: Repeat the question until a valid number is provided.\n6. Read back the patient's entire phone number, one digit at a time, to ensure you heard it correctly.\n7. You must then ask the patient a follow-up question specific to their current eye emergency.\n8. Then, ask the patient if there is anything else they'd like to add.\n9. Finally, thank the patient for their time. Inform the patient a message is being sent to the on-call Doctor.\n\nUse short sentences in your responses. Collect the information one piece at a time, in English only.\n\nIf you understand the instructions, reply \"Welcome to Shasta Professional Eye Care. My name is Eva. How can I help you today?\".\n",
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f'Here is the description of the agent instruction prompt to make:\n{agent_description}\n\n\n\nNow make instructions for an agent, {name}, that takes calls for {employer}, as a {job_title} doing the above. The first message the agent should say is "{base_message}".',
                    }
                ],
            },
        ],
    )
    return message.content[0].text


class CreateAgent(
    BaseAction[CreateAgentActionConfig, CreateAgentParameters, CreateAgentResponse]
):
    description: str = "Create an agent"
    parameters_type: Type[CreateAgentParameters] = CreateAgentParameters
    response_type: Type[CreateAgentResponse] = CreateAgentResponse

    async def run(
        self, action_input: ActionInput[CreateAgentParameters]
    ) -> ActionOutput[CreateAgentResponse]:
        query = f"""
            query createAgent_sourceAgentQuery($ai_profile_id: bigint!) {{
                ai_profiles_by_pk(id: $ai_profile_id) {{
                    company_id
                    integrations
                    job_title
                    language
                    model_name
                    name
                    use_filler_words
                    use_streaming
                    voice_id
                    voice_provider
                    user_plaintext_prompt
                    employer
                    gender
                    creator_id
                    async_integrations
                    allow_interruptions
                }}
            }}
        """

        variables = {"ai_profile_id": self.action_config.ai_profile_id}

        response = await execute_graphql_query(query, variables)
        data = response.get("data", {}).get("ai_profiles_by_pk", {})
        logger.info(f"Query response0: {data}")
        company_id = data["company_id"]
        integrations = data["integrations"]
        # job_title = data.get("job_title ", None)
        language = data["language"] if "language" in data else None
        model_name = data["model_name"] if "model_name" in data else None
        source_agent_name = data["name"] if "name" in data else None
        use_filler_words = (
            data["use_filler_words"] if "use_filler_words" in data else None
        )
        use_streaming = data["use_streaming"] if "use_streaming" in data else None
        voice_id = data["voice_id"] if "voice_id" in data else None
        voice_provider = data["voice_provider"] if "voice_provider" in data else None
        user_plaintext_prompt = (
            data["user_plaintext_prompt"] if "user_plaintext_prompt" in data else None
        )
        # employer = data.get("employer ", None)
        # gender = data.get("gender ", None)
        creator_id = data["creator_id"] if "creator_id" in data else None
        async_integrations = (
            data["async_integrations"] if "async_integrations" in data else None
        )
        # allow_interruptions = data.get("allow_interruptions ", None)

        # HI OLIVER THIS IS WHERE YOU SHOULD IMPLEMENT THE PROMPT GENERATION
        prompt = await generate_prompt(
            name=action_input.params.name,
            job_title=action_input.params.job_title,
            employer=action_input.params.employer,
            agent_description=action_input.params.agent_description,
            base_message=action_input.params.base_message,
        )
        mutation = """mutation MyMutation($allow_interruptions: Boolean, $base_message: String!, $company_id: bigint!, $creator_id: bigint, $employer: String, $gender: String, $job_title: String, $language: String, $model_name: String, $name: String, $voice_id: String, $voice_provider: String, $use_filler_words: Boolean, $use_streaming: Boolean, $prompt: String!) {
  insert_ai_profiles_one(object: {company_id: $company_id, creator_id: $creator_id, employer: $employer, gender: $gender, job_title: $job_title, language: $language, model_name: $model_name, name: $name, voice_id: $voice_id, voice_provider: $voice_provider, user_plaintext_prompt: $prompt, use_streaming: $use_streaming, use_filler_words: $use_filler_words, allow_interruptions: $allow_interruptions, base_message: $base_message}) {
    name
  }
}"""

        variables = {
            "allow_interruptions": action_input.params.allow_interruptions,
            # "async_integrations": async_integrations,
            "base_message": action_input.params.base_message,
            "company_id": company_id,
            "creator_id": creator_id,
            "employer": action_input.params.employer,
            "gender": action_input.params.gender,
            # "integrations": {},
            "job_title": action_input.params.job_title,
            "language": language,
            "model_name": model_name,
            "name": action_input.params.name,
            "voice_id": voice_id,
            "voice_provider": voice_provider,
            "use_filler_words": use_filler_words,
            "use_streaming": use_streaming,
            "prompt": prompt,
        }
        # log the var
        logger.info(f"Query variables: {variables}")
        # log query repponse
        logger.info(f"Query response: {response}")

        await execute_graphql_query(mutation, variables)

        return ActionOutput(
            action_type=action_input.action_config.type,
            response=CreateAgentResponse(
                success=True,
                message="Agent has been created successfully!",
            ),
        )
