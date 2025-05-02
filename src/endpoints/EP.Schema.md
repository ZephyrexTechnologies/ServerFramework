# API Endpoint Schema

- Braces in a URL mean that that param name of the body object is pulled from that slug of the URL.
- Non-standard implementations are flagged with an exclamation mark.
- Typical entities support the basic POST (Create), GET (List, supporting pagination, sort_by and sort_order), GET/ID (Read), PUT (Update) and DELETE (Delete) endpoints. They also support a `/search` POST which allows for advanced search criteria on specific fields.
- GET endpoints also all support a `fields` param which determines what fields to include in the response.
- Typical entities support batch POST, PUT and DELETE via request to the bulk endpoints with the following bodies:
	- POST: `{entity_name_plural: [{}, {}, {}]}` (also accepts `{entity_name: {}}`)
	- PUT: `{entity_name: {}, target_ids: ["", "", ""]}`
	- DELETE: Query Parameter: `?target_ids=id1,id2,id3`

## Authentication Domain

### User Router 

- Create (Register) a User [None / Basic]
    - POST /v1/user
- Login a User [Basic]
    - !POST /v1/user/authorize
        - Authenticates a user and returns a JWT token after creating a session
- Get a User
	- !GET /v1/user
		- Gets the requesting user (singular), as opposed to a list.
    - GET /v1/user/{id}
- List Users
    - GET /v1/team/{team_id}/user
	    - Listing all users the requester has access to without a `team_id` is not supported.
- Update a User
    - !PUT /v1/user
        - Updates the requesting user (singular), as opposed to bulk processing.
- Delete a User
    - !DELETE /v1/user
        - Deletes the requesting user (singular), as opposed to bulk processing.
- Change User Password
    - !PATCH /v1/user
        - Changes the current user's password.
- Verify Authorization
    - !GET /v1
        - Verifies a JWT or API Key is valid (for something), and returns a 204 status if so, and a 401 if not. 
    - !PATCH /v1
        - Refreshes the current session.
    - !DELETE /v1
        - Terminates the current session.
- Terminate a Specific Session
    - !DELETE /v1/user/session/{session_id}
- Terminate All Sessions
    - !DELETE /v1/user/session
- List All Sessions
    - !GET /v1/user/session
- Get a Session
    - !GET /v1/user/session/{session_id}

### Team Router [JWT]

- Create a Team
    - POST /v1/team
    - POST /v1/team/{team_id}/team
- Get a Team
    - GET /v1/team/{id}
- List Teams
    - GET /v1/team
    - GET /v1/team/{team_id}/team
- Update a Team
    - PUT /v1/team/{id}
    - PUT /v1/team
        - Bulk processing of updates.
- Delete a Team
    - DELETE /v1/team/{id}
    - DELETE /v1/team
        - Bulk processing of updates
- Get Team Users
    - !GET /v1/team/{id}/user
        - Retrieves users in a team
- Update User Role in Team
    - !PUT /v1/team/{id}/user/{user_id}/role
- Search Teams
    - POST /v1/team/search

### Role Router [JWT]
- Create a Role
    - POST /v1/team/{team_id}/role
- Get a Role
    - GET /v1/role/{id}
- List Roles
    - GET /v1/team/{team_id}/role
- Update a Role
    - PUT /v1/role/{id}
- Delete a Role
    - DELETE /v1/role/{id}
- Search Roles
    - POST /v1/team/{team_id}/role/search

### Invitation Router [JWT]
- Create an Invitation
    - POST /v1/invitation
    - POST /v1/team/{team_id}/invitation
- Get an Invitation
    - GET /v1/invitation/{id}
- List Invitations
    - GET /v1/invitation
    - GET /v1/team/{team_id}/invitation
- Update an Invitation
    - PUT /v1/invitation/{id}
    - PUT /v1/invitation
        - Bulk processing of updates.
- Delete an Invitation
    - DELETE /v1/invitation/{id}
    - DELETE /v1/invitation
        - Bulk processing of updates
    - !DELETE /v1/team/{team_id}/invitation
        - Revokes ALL open invitations.
- Search Invitations
    - POST /v1/invitation/search
- Accept an Invitation
    - PATCH /v1/invitation/{id}

### Notification Router [JWT]

- Create a Notification
    - POST /v1/user/notification
- Get a Notification
    - GET /v1/user/notification/{id}
- List Notifications
    - GET /v1/user/notification
- Update a Notification
    - PUT /v1/user/notification/{id}
    - PUT /v1/user/notification
        - Bulk processing of updates.
- Delete a Notification
    - DELETE /v1/user/notification/{id}
    - DELETE /v1/user/notification
        - Bulk processing of updates
- Search Notifications
    - POST /v1/user/notification/search

### API Key Router [JWT]

- Create an API Key
    - POST /v1/key
- Get an API Key
    - GET /v1/key/{id}
- List API Keys
    - GET /v1/key
- Update an API Key
    - PUT /v1/key/{id}
    - PUT /v1/key
        - Bulk processing of updates.
- Delete an API Key
    - DELETE /v1/key/{id}
    - DELETE /v1/key
        - Bulk processing of updates
- Generate API Key
    - !POST /v1/key/generate
        - Generates a new API key
- Validate API Key
    - !POST /v1/api/validate
        - Validates an API key
- Search API Keys
    - POST /v1/key/search

### User Merge Router [JWT]

- Merge Users
    - !POST /v1/user/merge
        - Merges two user accounts


## Conversations Domain

### Conversation Router [JWT]

- Create a Conversation
    - POST /v1/conversation
    - POST /v1/project/{project_id}/conversation
- Get a Conversation
    - GET /v1/conversation/{id}
- List Conversations
    - GET /v1/conversation
- Search Conversations
    - POST /v1/conversation/search
- Update a Conversation
    - PUT /v1/conversation/{id}
    - PUT /v1/conversation
        - Bulk processing of updates.
    - !PATCH /v1/conversation
        - Automatically renames a conversation based on its content
- Delete a Conversation
    - DELETE /v1/conversation/{id}
    - DELETE /v1/conversation
        - Bulk processing of updates

### Message Router [JWT]

- List Messages
    - GET /v1/message
    - GET /v1/conversation/{conversation_id}/message
- Get a Specific Message
    - GET /v1/message/{id}
- Create a Message
    - POST /v1/message
    - POST /v1/conversation/{conversation_id}/message
- Update a Message
    - PUT /v1/message/{id}
    - PUT /v1/message
        - Bulk processing of updates.
    - !PATCH /v1/conversation/{conversation_id}/message
        - Forks a message by creating a new message with the same parent with the revised content, then submitting a new completion therefrom.
- Delete a Message
    - DELETE /v1/message/{id}
    - DELETE /v1/message
        - Bulk processing of updates
- Search Messages
    - POST /v1/message/search

### Artifact Router [JWT]

- Create an Artifact
    - POST /v1/artifact
    - POST /v1/project/{project_id}/artifact
    - POST /v1/conversation/{conversation_id}/artifact
- Get an Artifact
    - GET /v1/artifact/{id}
- List Artifacts
    - GET /v1/artifact
    - GET /v1/project/{project_id}/artifact
    - GET /v1/conversation/{conversation_id}/artifact
- Update an Artifact
    - PUT /v1/artifact/{id}
    - PUT /v1/artifact
        - Bulk processing of updates.
- Delete an Artifact
    - DELETE /v1/artifact/{id}
    - DELETE /v1/artifact
        - Bulk processing of updates
- Search Artifacts
    - POST /v1/artifact/search

### Activity Router [JWT]

- Create an Activity
    - POST /v1/activity
    - POST /v1/activity/{activity_id}/activity
    - POST /v1/message/{message_id}/activity
- Get an Activity
    - GET /v1/activity/{id}
- List Activities
    - GET /v1/activity
    - GET /v1/message/{message_id}/activity
- Update an Activity
    - PUT /v1/activity/{id}
    - PUT /v1/activity
        - Bulk processing of updates.
- Delete an Activity
    - DELETE /v1/activity/{id}
    - DELETE /v1/activity
        - Bulk processing of updates
- Search Activities
    - POST /v1/activity/search

### Feedback Router [JWT]

- Create Feedback
    - POST /v1/feedback
    - POST /v1/message/{message_id}/feedback
- Get Feedback
    - GET /v1/feedback/{id}
- List Feedback
    - GET /v1/feedback
    - GET /v1/message/{message_id}/feedback
- Update Feedback
    - PUT /v1/feedback/{id}
    - PUT /v1/feedback
        - Bulk processing of updates.
- Delete Feedback
    - DELETE /v1/feedback/{id}
    - DELETE /v1/feedback
        - Bulk processing of updates
- Search Feedback
    - POST /v1/feedback/search

## Project Domain

### Project Router [JWT]

- Create a Project
    - POST /v1/project
    - POST /v1/project/{project_id}/project
- Get a Project
    - GET /v1/project/{id}
- List Projects
    - GET /v1/project
    - GET /v1/project/{project_id}/project
- Update a Project
    - PUT /v1/project/{id}
    - PUT /v1/project
        - Bulk processing of updates.
- Delete a Project
    - DELETE /v1/project/{id}
    - DELETE /v1/project
        - Bulk processing of updates
- Search Projects
    - POST /v1/project/search


## Providers Domain

### Provider Extension Router [JWT]

- Create a Provider Extension
    - POST /v1/provider/extension
- Get a Provider Extension
    - GET /v1/provider/extension/{id}
- List Provider Extensions
    - GET /v1/provider/extension
- Update a Provider Extension
    - PUT /v1/provider/extension/{id}
    - PUT /v1/provider/extension
        - Bulk processing of updates.
- Delete a Provider Extension
    - DELETE /v1/provider/extension/{id}
    - DELETE /v1/provider/extension
        - Bulk processing of updates
- Search Provider Extensions
    - POST /v1/provider/extension/search

### Provider Router [JWT]

- Create a Provider
    - POST /v1/provider
- Get a Provider
    - GET /v1/provider/{id}
- List Providers
    - GET /v1/provider
- Update a Provider
    - PUT /v1/provider/{id}
    - PUT /v1/provider
        - Bulk processing of updates.
- Delete a Provider
    - DELETE /v1/provider/{id}
    - DELETE /v1/provider
        - Bulk processing of updates
- Search Providers
    - POST /v1/provider/search

### Provider Instance Router [JWT]

- Create a Provider Instance
    - POST /v1/provider/{provider_id}/instance
- Get a Provider Instance
    - GET /v1/provider/{provider_id}/instance/{id}
- List Provider Instances
    - GET /v1/provider/{provider_id}/instance
- Update a Provider Instance
    - PUT /v1/provider/{provider_id}/instance/{id}
    - PUT /v1/provider/{provider_id}/instance
        - Bulk processing of updates.
- Delete a Provider Instance
    - DELETE /v1/provider/{provider_id}/instance/{id}
    - DELETE /v1/provider/{provider_id}/instance
        - Bulk processing of updates
- Search Provider Instances
    - POST /v1/provider/{provider_id}/instance/search

### Rotation Router [JWT]

- Create a Rotation
    - POST /v1/rotation
- Get a Rotation
    - GET /v1/rotation/{id}
- List Rotations
    - GET /v1/rotation
- Update a Rotation
    - PUT /v1/rotation/{id}
    - PUT /v1/rotation
        - Bulk processing of updates.
- Delete a Rotation
    - DELETE /v1/rotation/{id}
    - DELETE /v1/rotation
        - Bulk processing of updates
- Search Rotations
    - POST /v1/rotation/search
