INTERRUPTION_PROMPT = """
**Objective:**

Your primary task is to detect instances where the customer intends to interrupt the rep to stop the ongoing conversation. You only get the words said by customer and you have to base your decision on them.

You must differentiate between two types of customer interjections:

1. **Non-interrupting acknowledgements**: These are phrases which signify the customer is following along but does not wish to interrupt the rep. Are close to words like this:

"Ok"
"Got it"
"Understood"
 "I see"
"Right"
"I follow"
"Yes"
"I agree"
"That makes sense"
"Sure"
"Sounds good"
"Indeed"
"Absolutely"
"Of course"
"Go on"
"Keep going"
"I'm with you"
"Continue"
"That's clear"
"Perfect"

2. **Interrupting requests**: These include phrases indicating the customer's desire to interrupt the conversation.
Are close to words like this:
"Please, stop"
"stop"
"hold"
"No, no"
"Wait"
"what"
"No"
"Hold on"
"That's not right"
"I disagree"
"Just a moment"
"Listen"
"That's incorrect"
"I need to say something"
"Excuse me"
"Stop for a second"
"Hang on"
"That's not what I meant"
"Let me speak"
"I have a concern"
"That doesn't sound right"
"I need to correct you"
"Can I just say something"
"I don't think so"
"You're misunderstanding"

**Input Specification:**

You get words said by the customer.


**Output Specification:**

You must return a JSON object indicating whether the rep should be interrupted based on the customer's interjections.

- Return `{"interrupt": "true"}` if the customer's interjection is an interrupting request.
- Return `{"interrupt": "false"}` if the customer's interjection is a non-interrupting acknowledgement.


RULES: 
IF the customer is saying some information about his situation, assume interruption is needed and set it to TRUE.


Example of output:
{"interrupt": "true"}
"""