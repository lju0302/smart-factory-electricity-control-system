import os
import json
from dotenv import load_dotenv
from azure.eventhub import EventHubConsumerClient

load_dotenv()

CONNECTION_STR = os.getenv("EVENTHUB_CONNECTION_STR")
EVENTHUB_NAME = os.getenv("EVENTHUB_NAME")
CONSUMER_GROUP = "$Default"


def on_event(partition_context, event):
    body = event.body_as_str(encoding="UTF-8")

    try:
        data = json.loads(body)
        print("Received:", data)
    except json.JSONDecodeError:
        print("Invalid JSON:", body)

    partition_context.update_checkpoint(event)


client = EventHubConsumerClient.from_connection_string(
    conn_str=CONNECTION_STR,
    consumer_group=CONSUMER_GROUP,
    eventhub_name=EVENTHUB_NAME,
)

with client:
    client.receive(
        on_event=on_event,
        starting_position="-1",
    )