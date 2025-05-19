# Work In Progress (not fully tested)

# ReleaseDockerDeployTelegram
Deploy a release from a notify bot on telegram

Need a forgejo instance (or adapt for ci targeted)

![Screenshot](IMG_4697.jpg)

# How it works

The script crons each hour to scan new release from dokcer hub.
If a new tag is created on a dokcer hub 's repo added a notification will be sent.

An action button under notification will create a tag on a instance forgejo.
With a configurated pipeline, a deployment will be activated by that.


# Start
- Create a directory in base directory project bot_data/
  A json will save data in this directory.

- Create a telegram Bot and get token

- Add token in config.py file

- Start the app

`docker compose build; docker compose up -d`


