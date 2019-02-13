# FalcomBot Cogs

Useful utilities I created for the Falcom discord, but anyone can use these ones here that are complete and functioning!

# Contents

- Topic (`topic`): A topic command for presenting the current topic to users, and setting the topic (allowing easier input of emojis and mentions).
    - `[p]topic [channel]`: Get channel topic. If omitted, use current channel.
    - [mod] `[p]topic set <channel> topic`: Set channel topic.
    - [mod] `[p]topic amend <channel> topic`: Amend to channel topic, placing new text after newline.
    - [mod] `[p]topic clear [channel]`: Clear channel topic. If omitted, use current channel.

- Random Tools (`randt`): Commands for various randomization tasks.
    - `[p]rolldice <dice>`
    - `[p]pick <item> <item> ...`
    - `[p]pickx <n> <item> <item> ...`
    - `[p]drawx <n> <item> <item> ...`
    - `[p]mix <item> <item> ...`

- FANDOM Wiki (`wikia`): A command to retrieve detailed, formatted preview content from a FANDOM Wiki page.
    - `[p]wiki -w <subdomain> <page name>`: Lookup page. "`-w <subdomain>`" part is optional if a default is set for a server.
    - [mod] `[p]wikiset default <subdomain>`

- Role Requests (`rolereqs`): A system for displaying and allowing users to request moderator-whitelisted list of roles.
    - `[p]req <role_name>`/`[p]req add <role_name>`: Request a role.
    - `[p]req rem <role_name>`: Remove requestable role.
    - `[p]req clear`: Remove all requestable roles.
    - `[p]req list`: List all requestable roles.
    - [mod] `[p]req addrole <role_name>`: Add a role to requestable.
    - [mod] `[p]req remrole <role_name>`: Remove a role from requestable.
    - [mod] `[p]req postlist <channel>`: Posts an automatically updating list of roles to a channel, for example a public one for users to see their selection.
    - [mod] `[p]req massadd <limit> <channel> <role_name>`: Inspect the last `<limit>` messages for participation and add `<role_name>` to the found users.
    - [mod] `[p]reqset channel <channel>`: [default: ] Set the channel that `[p]reqset list` and `[p]reqset postlist` reference.
    - [mod] `[p]reqset max_requestable <limit>`: [default: 3] Set the maximum number of requestable roles the bot allows adding to a user. A moderator can still freely apply more than set here.
    - [mod] `[p]reqset auto_post_list [bool]`: [default: true] Set whether post lists are updated automatically when users change their roles using `[p]request`.

- ROT-13 (`rot13`): ROT-13 encoding and decoding system, allowing users to use an emoji react to instantly decode privately.
    - `[p]rot13 <text>`: Encode/decode the given text.
    - [mod] `[p]req13set dm_rot13 [bool]`: [default: true] Whether to DM users ROT-13ed text when they react with :unlock:.
    - [mod] `[p]req13set auto_react_to [bool]`: [default: ] If set to a non-empty string, the bot auto-reacts to messages containing the string with :unlock:. Suggested usage: set it to "rot13" and let users prefix their encoded text with it and the bot allows one-tap decoding.


# Installation

1. `[p]repo add falcogs https://github.com/nmbook/FalcomBot-cogs`
2. `[p]cog list falcogs`
3. `[p]cog install falcogs <cog_name>`
4. `[p]load <cog_name>`
5. `[p]help <cog_name>`

# Credits

- [Twentysix26](https://github.com/Twentysix26): Twentysix and the other developers of Red made a platform for randoms like me to add features as wanted.
- Gu4n, Twililord, and others: Ideas on how to do Wikia and spoiler cogs.

# Contact

I'm on Discord as **Ribose#1423**.

