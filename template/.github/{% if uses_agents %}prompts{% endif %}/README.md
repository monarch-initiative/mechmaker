# Agent prompts

One prompt per agent workflow. `render_prompt.py` fills `${NAME}`
placeholders from `PROMPT_<NAME>` variables the workflow sets: repository,
numbers, flags. Nothing written by other people is ever pasted in.

Edit these to fit the Mech. They are read from the default branch, so a pull
request cannot change the prompt it is reviewed under. Keep the "untrusted
content" paragraph in every prompt that reads issues, pull requests or
comments.
