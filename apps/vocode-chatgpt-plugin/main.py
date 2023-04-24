import os
from dotenv import load_dotenv

load_dotenv()

import logging
import json

import quart
import quart_cors
from quart import request
from pydantic import BaseModel

from vocode.streaming.telephony.config_manager.redis_config_manager import (
    RedisConfigManager,
)
from vocode.streaming.telephony.conversation.outbound_call import OutboundCall
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.message import BaseMessage


app = quart_cors.cors(quart.Quart(__name__), allow_origin="https://chat.openai.com")

config_manager = RedisConfigManager()

TELEPHONY_BASE_URL = "b42a46e72b22.ngrok.app"


class CreateOutboundCall(BaseModel):
    recipient_number: str
    gpt_prompt: str = ""
    initial_message: str


@app.post("/call")
async def outbound_call():
    request = await quart.request.get_json(force=True)
    request = CreateOutboundCall(**request)
    call = OutboundCall(
        base_url=TELEPHONY_BASE_URL,
        to_phone=request.recipient_number,
        from_phone="+16507299536",
        config_manager=config_manager,
        agent_config=ChatGPTAgentConfig(
            prompt_preamble=request.gpt_prompt,
            end_conversation_on_goodbye=True,
            initial_message=BaseMessage(text=request.initial_message),
        ),
        logger=logging.Logger("call_phone_number"),
    )
    call.start()
    resp = {"success": True, "conversation_id": call.conversation_id}
    print(json.dumps(resp))
    return quart.Response(
        response=json.dumps(resp),
        status=200,
    )


@app.get("/transcript/<string:conversation_id>")
async def transcript(conversation_id: str):
    print(conversation_id)
    if not os.path.exists("call_transcripts/{}.txt".format(conversation_id)):
        response = {
            "success": False,
            "transcript": "Transcript not found for conversation_id: {}".format(
                conversation_id
            ),
        }
    else:
        with open("call_transcripts/{}.txt".format(conversation_id)) as f:
            transcript = f.read()
            response = {
                "success": True,
                "transcript": transcript,
            }
    return quart.Response(response=json.dumps(response), status=200)


@app.get("/logo.png")
async def plugin_logo():
    filename = "logo.png"
    return await quart.send_file(filename, mimetype="image/png")


@app.get("/.well-known/ai-plugin.json")
async def plugin_manifest():
    host = request.headers["Host"]
    with open("./.well-known/ai-plugin.json") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/json")


@app.get("/openapi.yaml")
async def openapi_spec():
    host = request.headers["Host"]
    with open("openapi.yaml") as f:
        text = f.read()
        return quart.Response(text, mimetype="text/yaml")


def main():
    app.run(debug=True, host="0.0.0.0", port=5003)


if __name__ == "__main__":
    main()
