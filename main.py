import json
import logging
import re
import os
import openai
from threading import Event
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

logging.basicConfig(level=logging.WARN)


class CharacterChatBot:
    def __init__(self, character_json_path):
        self.client = SocketModeClient(
            app_token=os.environ['SLACK_APP_TOKEN'],
            web_client=WebClient(token=os.environ['SLACK_TOKEN'])
        )
        openai.api_key = os.environ['OPENAI_API_KEY']

        self.character_data = {}
        with open(character_json_path) as f:
            self.character_data = json.load(f)

        self.prefix = f"以下は{self.character_data['name']}の設定です。\n\n"
        for overview in self.character_data['overview']:
            self.prefix += overview + "\n"

        self.prefix += f"\n以下は{self.character_data['name']}のセリフです。\n\n"
        for serif in self.character_data['serif']:
            self.prefix += f"{self.character_data['name']}「{serif}」\n"

        self.prefix += f"\n{self.character_data['name']}っぽく、以下に返答してください。\n"
        self.history = ""

        self.client.socket_mode_request_listeners.append(self.process)
        self.client.connect()

    def wait_event(self):
        Event().wait()

    def process(self, cli: SocketModeClient, req: SocketModeRequest):
        response = SocketModeResponse(envelope_id=req.envelope_id)
        self.client.send_socket_mode_response(response)

        if req.type != "events_api":
            return
        event = req.payload.get("event")
        if event["type"] != "app_mention":
            return
        text = re.sub('<@.+>', '', event["text"])

        # ChatGPTにテキストを送信し、返信を受け取る
        content = "マスター「" + text + "」"
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=self.prefix + self.history + content,
            max_tokens=1024,
            temperature=0.5,
        )

        # ChatGPTから返信を受け取ったテキストを取得する
        response_text = response["choices"][0]["text"]

        self.history += content + "\n"
        self.history += response_text + "\n"

        sending_text = re.sub(f"^\n*{self.character_data['name']}「", '', response_text, 1)
        sending_text = re.sub('」$', '', sending_text)

        # Slackに返信を送信する
        cli.web_client.chat_postMessage(channel=event["channel"], text=sending_text)


if __name__ == '__main__':
    bot = CharacterChatBot("./character.json")
    bot.wait_event()

