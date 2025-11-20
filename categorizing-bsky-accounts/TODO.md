We're going to edit this skill to make use of the existing extracting-keywords skill:

This skill will act as an agentic wrapper, invoking the extractong-keywords skill in a for each account to analyze

First this skill will get the account(s) to analyze 
 - Claude will determine which code to invoke to get the individual accounts to examine (individual account(s), bsky list, account's follows/followers, or uploaded file?) and whether to use a specialized stopwords list
 - The code will start a working file with account details which will not be processed by Claude (indexed by account id for ease of later lookup) -- name, bio, avatar
 - The code will loop through the accounts (max N, default 100) and for each
   - Extract the top M (default 20) messages from that account
   - combine the text, then
   - invoke extract-keyword with appropriate settings (extract say 10 keywords by default?)
   - Claude will then using just the account id, bio from first working file and the keywords list categorize the account from the keywords in a new working file: account id, category

After the loop 
- Claude will optionally filter the account by some desired category
-  code will be run to combine the two working files to augment category file with user names, avatar, link to profile etc, and the ouput provided to the user

### SKILL.md

1. **Prerequisites section** - change to:
   ```markdown
   ## Prerequisites
   
   **Requires:** extracting-keywords skill (provides YAKE venv + domain stopwords)
   ```
