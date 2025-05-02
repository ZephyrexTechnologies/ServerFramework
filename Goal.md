# Mixins
- [X] Allow for favouriting and tagging of conversations/agents/chains/prompts. Favouriting must be on a per-user basis, tags can be on a per-entity basis (CSV?).
- [X] Allow for images to be uploaded for agents and companies as well as users.
- [X] Custom webhook terminations to invoke chains/prompts.
# Agents
# Chains
# Conversations
- [X] Implement proper conversation forking and regeneration via edit (messages have a parent message).
- [X] Project organization, similar to v0, including project-based prompt injection for frameworks/etc.
- [X] Canvas editor for markdown including feedback of certain sections, improve/explain. 
- [X] A/B testing of replies.
- [X] Add a way to tell if a completion is still processing so if the page is left and revisited the state can correctly reflect this.
# Extensions
- [ ] Allow company extensions/commands to be "Force Off" / "Available" (toggleable at user level) / "Force On".
- [ ] Allow Team, Agent and User level extensions/commands (logging in etc).
# Prompts
- [X] Multiple contexts for agents, and check them off to apply or not.
# Providers
- [X] Allow providers to be enabled/disabled in addition to disconnection, so as not to erase keys. Team level providers should also be included in the  agent provider UI both for clarity of what is available, and to disable them atomically in the event you want to use a different key for only one agent. 
# Tasks
# Auth
- [ ] Nullable permissions to allow for clear/explicit yes/explicit no.
- [ ] Proper notifications, nullable foreign key to message, but also other relevant tables like Agent and Provider. 
- [ ] Allow for explicit sharing and marketplace of agents/chains/prompts.
- [ ] Custom scoped API keys to accounts / agents. 
- [ ] Attempt to include a FastAPI router in each table object similar to how the CRUD functions are set up, with a callback to inject additional functionality into endpoints where required.
