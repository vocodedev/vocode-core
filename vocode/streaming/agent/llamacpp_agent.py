raise DeprecationWarning("This Agent is deprecated and will be removed in the future.")

# OLD CONFIG BELOW
# class LlamacppAgentConfig(AgentConfig, type=AgentType.LLAMACPP.value):  # type: ignore
#     prompt_preamble: str
#     llamacpp_kwargs: dict = {}
#     prompt_template: Optional[Union["PromptTemplate", str]] = None

# ALPACA_TEMPLATE_WITH_HISTORY = """### Instruction:
# Your previous conversation history:
# {history}

# Current instruction/message to respond to: {input}
# ### Response:"""


# class CallbackOutput(BaseModel):
#     finish: bool = False
#     response: Optional[LLMResult] = None
#     token: str = ""


# class FormatHistoryPromptTemplate(PromptTemplate):
#     def format(self, **kwargs: Any) -> str:
#         kwargs = self._merge_partial_and_user_variables(**kwargs)
#         kwargs["history"] = get_buffer_string(kwargs["history"])
#         return DEFAULT_FORMATTER_MAPPING[self.template_format](self.template, **kwargs)


# class CustomStreamingCallbackHandler(BaseCallbackHandler):
#     def __init__(self, output_queue: asyncio.Queue) -> None:
#         super().__init__()
#         self.output_queue = output_queue

#     def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
#         """Run on new LLM token. Only available when streaming is enabled."""
#         self.output_queue.put_nowait(CallbackOutput(token=token))

#     def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
#         """Run when LLM ends running."""
#         self.output_queue.put_nowait(CallbackOutput(finish=True, response=response))


# class LlamacppAgent(RespondAgent[LlamacppAgentConfig]):
#     def __init__(
#         self,
#         agent_config: LlamacppAgentConfig,
#     ):
#         super().__init__(agent_config=agent_config)

#         self.prompt: Union[PromptTemplate, ChatPromptTemplate]
#         if type(agent_config.prompt_template) is str:
#             if agent_config.prompt_template == "alpaca":
#                 self.prompt = FormatHistoryPromptTemplate(
#                     input_variables=["history", "input"],
#                     template=ALPACA_TEMPLATE_WITH_HISTORY,
#                 )
#             else:
#                 raise ValueError(f"Unknown prompt template {agent_config.prompt_template}")
#         else:
#             if agent_config.prompt_template is None:
#                 self.prompt = ChatPromptTemplate.from_messages(
#                     [
#                         MessagesPlaceholder(variable_name="history"),
#                         HumanMessagePromptTemplate.from_template("{input}"),
#                     ]
#                 )
#             else:
#                 self.promt = typing.cast(PromptTemplate, agent_config.prompt_template)

#         self.callback_queue: asyncio.Queue = asyncio.Queue()
#         callback = CustomStreamingCallbackHandler(self.callback_queue)
#         callback_manager = CallbackManager([callback])
#         self.llm = LlamaCpp(callback_manager=callback_manager, **agent_config.llamacpp_kwargs)

#         self.memory = ConversationBufferMemory(return_messages=True)
#         self.memory.chat_memory.messages.append(
#             SystemMessage(content=self.agent_config.prompt_preamble)
#         )

#         self.conversation = ConversationChain(memory=self.memory, prompt=self.prompt, llm=self.llm)
#         self.thread_pool_executor = ThreadPoolExecutor(max_workers=1)

#     async def respond(
#         self,
#         human_input,
#         conversation_id: str,
#         is_interrupt: bool = False,
#     ) -> Tuple[str, bool]:
#         text = await asyncio.get_event_loop().run_in_executor(
#             self.thread_pool_executor,
#             lambda input: self.conversation.predict(input=input),
#             human_input,
#         )

#         logger.debug(f"LLM response: {text}")
#         return text, False

#     async def llamacpp_get_tokens(self):
#         while True:
#             callback_output = await self.callback_queue.get()
#             if callback_output.finish:
#                 break
#             yield callback_output.token

#     async def generate_response(
#         self,
#         human_input: str,
#         conversation_id: str,
#         is_interrupt: bool = False,
#     ) -> AsyncGenerator[Tuple[str, bool], None]:
#         asyncio.get_event_loop().run_in_executor(
#             self.thread_pool_executor,
#             lambda input: self.conversation.predict(input=input),
#             human_input,
#         )

#         async for message in collate_response_async(
#             self.llamacpp_get_tokens(),
#         ):
#             yield str(message), True
