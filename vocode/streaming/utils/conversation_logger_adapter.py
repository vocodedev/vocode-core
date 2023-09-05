# A logger adapter that adds a conversation_id to the log message.

import logging

class ConversationLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['conversation_id'], msg), kwargs

def wrap_logger(logger, conversation_id):
    if isinstance(logger, ConversationLoggerAdapter):
        return logger
    else:
      return ConversationLoggerAdapter(logger, {'conversation_id': conversation_id})
