import os
from dataclasses import dataclass
from typing import Generator
import re
import time
from datetime import datetime

from mailbox import mbox

from email.utils import format_datetime, make_msgid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.message import EmailMessage

import requests

API_KEY = os.environ.get("API_KEY")
API_BASE = os.environ.get("API_BASE")
LIST_NAME = os.environ.get("LIST_NAME")

headers = {"Api-Key": API_KEY, "Api-Username": "system"}

users = {
    user["id"]: user["email"]
    for user in requests.get(
        API_BASE + f"/admin/users/list/active.json?show_emails=true", headers=headers
    ).json()
}


@dataclass
class Message:
    user_identifier: int
    content: str
    html: str
    date: datetime
    links: list[str]

    @property
    def email(self):
        return users[self.user_identifier]


@dataclass
class Thread:
    title: str
    identifier: int
    messages: Generator[Message, None, None]


def get_messages(identifier: str):
    data = requests.get(
        API_BASE + f"/t/{identifier}.json",
        headers=headers,
        params={"include_raw": True},
    ).json()

    if not "post_stream" in data:
        print(data)

        # Honor rate limit
        time.sleep(data["extras"]["wait_seconds"] + 1)

        data = requests.get(
            API_BASE + f"/t/{identifier}.json",
            headers=headers,
            params={"include_raw": True},
        ).json()

    messages = data["post_stream"]["stream"]
    while messages:
        data = requests.get(
            API_BASE + f"/t/{identifier}.json",
            headers=headers,
            params={"include_raw": True, "post_stream": messages[:20]},
        ).json()
        del messages[:20]

        for message in data["post_stream"]["posts"]:
            yield Message(
                user_identifier=message["user_id"],
                content=message["raw"],
                date=datetime.fromisoformat(message["created_at"]),
                html=message["cooked"],
                links=[
                    link["url"]
                    for link in message.get("link_counts", [])
                    if link["internal"]
                ],
            )


def get_threads() -> Generator[Thread, None, None]:
    response = requests.get(
        API_BASE + "top.json", params={"period": "all"}, headers=headers
    )

    topics = response.json()["topic_list"]["topics"]

    for topic in topics:
        identifier = topic["id"]

        thread = Thread(
            title=topic["title"],
            identifier=identifier,
            messages=get_messages(identifier),
        )

        yield thread


def create_mail(
    subject: str, message: Message, last_id=None
) -> tuple[EmailMessage, str]:
    message_id = make_msgid()

    mail = EmailMessage()

    mail["Subject"] = subject
    mail["From"] = message.email
    mail["To"] = LIST_NAME
    mail["Date"] = format_datetime(message.date)
    mail["message-id"] = message_id
    if last_id:
        mail["In-Reply-To"] = last_id

    # Remove broken attachment links
    content = message.content
    for pattern in [
        r"!?\[.*\]\((upload).*\)",
        r"!?\[.*\]\((data).*\)",
        r"!\[.*\]\(.*\)",
    ]:
        content = re.sub(
            pattern,
            "",
            content,
        )

    mail.set_content(content)

    # Add attachments
    for link in message.links:
        if link.startswith("/"):
            link = API_BASE + link
        result = requests.get(link)
        maintype, subtype = result.headers["content-type"].split("/")
        mail.add_attachment(
            result.content,
            maintype=maintype,
            subtype=subtype,
            filename=link.split("/")[-1],
        )

    return mail, message_id


box = mbox("test.mbox")
for thread in get_threads():
    last = None
    for message in thread.messages:
        mail, last = create_mail(thread.title, message, last)
        box.add(mail)

    break
