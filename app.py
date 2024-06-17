import os
from datetime import datetime
import streamlit as st
from dotenv import load_dotenv
from openai import AssistantEventHandler, OpenAI
from openai.types.beta.threads import Text, TextDelta
from typing_extensions import override

load_dotenv()

client = OpenAI()

# "gpt-3.5-turbo-16k"
model = "gpt-4-turbo"

# # Create a vector store caled "Cryptocurrency"
# vector_store = client.beta.vector_stores.create(name="Cryptocurrency")
#
# # Ready the files for upload to OpenAI
# file_paths = ["./cryptocurrency.pdf"]
# file_streams = [open(path, "rb") for path in file_paths]
#
# # Use the upload and poll SDK helper to upload the files, add them to the vector store,
# # and poll the status of the file batch for completion.
# file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
#     vector_store_id=vector_store.id,
#     files=file_streams,
# )
#
# print(f"File batch status: {file_batch.status}")
# print(f"File batch ID: {file_batch.id}")
# print(f"File count: {file_batch.file_counts}")

assistant_id = os.environ.get("OPENAI_ASST_ID")
if not assistant_id:
    # Step 2. Create an assistant
    assistant = client.beta.assistants.create(
        name="Study Buddy",
        instructions=f"""You are a helpful study assistant who knows a lot about understanding research papers.
        Your role is to summarize papers, clarify terminology within context, and extract key figures and data.
        Cross-reference information for additional insights and answer related questions comprehensively.
        Analyze the papers, noting strengths and limitations.
        Respond to queries effectively, incorporating feedback to enhance your accuracy.
        Handle data securely and update your knowledge base with the latest research.
        Adhere to ethical standards, respect intellectual property, and provide users with guidance on any limitations.
        Maintain a feedback loop for continuous improvement and user support.
        Your ultimate goal is to facilitate a deeper understanding of complex scientific material, making it more accessible and comprehensible.
        """,
        model=model,
        tools=[{"type": "file_search"}],
    )
    assistant_id = assistant.id
print(f"Assistant ID: {assistant_id}")

# Create a vector store caled "Cryptocurrency"
vector_store = client.beta.vector_stores.create(name="Blockchain")

# Ready the files for upload to OpenAI
file_paths = ["./blockchain.pdf"]
file_streams = [open(path, "rb") for path in file_paths]

# Use the upload and poll SDK helper to upload the files, add them to the vector store,
# and poll the status of the file batch for completion.
file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
    vector_store_id=vector_store.id,
    files=file_streams,
)

print(f"File batch status: {file_batch.status}")
print(f"File batch ID: {file_batch.id}")
print(f"File count: {file_batch.file_counts}")

assistant = client.beta.assistants.update(
    assistant_id=assistant_id,
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}}
)

thread_id = os.environ.get("OPENAI_ASST_THREAD_ID")
if not thread_id:
    thread = client.beta.threads.create()
    thread_id = thread.id
print(f"Thread ID: {thread_id}")

# message = "What is mining?"
# message = "What is a blockchain?"
# message = "How many Bitcoins can be in existence?"
message = "Cơ hội và thách thức khi áp dụng Blockchain vào logistics và chuỗi cung ứng ở Việt Nam?"
print(f"User: {message}")
client.beta.threads.messages.create(
    thread_id=thread_id,
    role="user",
    content=message,
)


class EventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text: Text) -> None:
        print(f"\nassistant > ", end="", flush=True)

    @override
    def on_tool_call_created(self, tool_call):
        print(f"\nassistant > {tool_call.type}\n", flush=True)

    @override
    def on_message_done(self, message) -> None:
        # print a citation to the file searched
        message_content = message.content[0].text
        annotations = message_content.annotations
        citations = []
        for index, annotation in enumerate(annotations):
            message_content.value = message_content.value.replace(
                annotation.text, f"[{index}]"
            )
            if file_citation := getattr(annotation, "file_citation", None):
                cited_file = client.files.retrieve(file_citation.file_id)
                citations.append(f"[{index}] {cited_file.filename}")

        print(message_content.value)
        print("\n".join(citations))


with client.beta.threads.runs.stream(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions="Please address the user as Nhã Đan.",
        event_handler=EventHandler(),
) as stream:
    stream.until_done()
