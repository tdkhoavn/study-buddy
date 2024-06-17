import os
import time
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

assistant_id = os.environ.get("OPENAI_ASST_ID")
thread_id = os.environ.get("OPENAI_ASST_THREAD_ID")

# Streamlit
if "file_ids_list" not in st.session_state:
    st.session_state.file_ids_list = []

if "start_chat" not in st.session_state:
    st.session_state.start_chat = False

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

st.set_page_config(
    page_title="Study Buddy - Chat and Learn",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="auto",
)


def create_vector_store(file_path):
    # Create a vector store
    vector_store_name = file_path.capitalize() + "_" + datetime.now().strftime("%Y%m%d%H%M%S")
    vector_store = client.beta.vector_stores.create(name=vector_store_name)

    with open(file_path, "rb") as file_stream:
        # Use the upload and poll SDK helper to upload the files, add them to the vector store,
        # and poll the status of the file batch for completion.
        file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id,
            files=[file_stream],
        )

        print(f"File batch status: {file_batch.status}")
        print(f"File batch ID: {file_batch.id}")
        print(f"File count: {file_batch.file_counts}")

        client.beta.assistants.update(
            assistant_id=assistant_id,
            tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
        )

        return file_batch.id


file_uploaded = st.sidebar.file_uploader(
    "Upload a file and add to a Vector Store",
    type=["pdf", "txt"],
    key="file_upload",
)

if st.sidebar.button("Upload File"):
    if file_uploaded:
        with open(f"{file_uploaded.name}", "wb") as file:
            file.write(file_uploaded.getbuffer())
        another_file_id = create_vector_store(f"{file_uploaded.name}")
        st.session_state.file_ids_list.append(another_file_id)
        st.sidebar.write(f"File ID: {another_file_id}")
        st.sidebar.success("File uploaded successfully!")

if st.session_state.file_ids_list:
    st.sidebar.write("Uploaded File IDs:")
    for file_id in st.session_state.file_ids_list:
        st.sidebar.write(file_id)

if st.sidebar.button("Start Chatting..."):
    if st.session_state.file_ids_list:
        st.session_state.start_chat = True

        thread = client.beta.threads.create()
        thread_id = thread.id
        st.session_state.thread_id = thread_id
        st.write("Thread ID:", thread_id)
    else:
        st.sidebar.warning("Please upload a file first!")


def process_message_with_citations(message_with_citations):
    """Extract content and annotations from the message and format citations as footnotes."""
    message_content = message_with_citations.content[0].text
    annotations = (
        message_content.annotations if hasattr(message_content, "annotations") else []
    )
    citations = []

    # Iterate over the annotations and add footnotes
    for index, annotation in enumerate(annotations):
        # Replace the text with a footnote
        message_content.value = message_content.value.replace(
            annotation.text, f" [{index + 1}]"
        )

        # Gather citations based on annotation attributes
        if file_citation := getattr(annotation, "file_citation", None):
            # Retrieve the cited file details (dummy response here since we can't call OpenAI)
            print(f"File Citation: {file_citation}")
            cited_file = client.files.retrieve(file_citation.file_id)
            print(f"Cited File: {cited_file}")
            citations.append(
                f'[{index + 1}] {cited_file.filename}'
            )
        elif file_path := getattr(annotation, "file_path", None):
            # Placeholder for file download citation
            cited_file = client.files.retrieve(file_citation.file_id)
            citations.append(
                f'[{index + 1}] Click [here](#) to download {cited_file.filename}'
            )  # The download link should be replaced with the actual download path

    # Add footnotes to the end of the message content
    full_response = message_content.value + "\n\n" + "\n".join(citations)
    return full_response


st.title("Study Buddy")
st.write("Learn fast by chatting with your documents")

if st.session_state.start_chat:
    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-4-turbo"
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What's new?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=prompt,
        )

        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=assistant_id,
            model=st.session_state.openai_model,
            instructions="""Please answer the questions using the knowledge provided in the files.
            when adding additional information, make sure to distinguish it with bold or underlined text."""
        )

        with st.spinner("Thinking..."):
            while run.status != "completed":
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id,
                )
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id
            )
            assistant_messages_for_run = [
                message
                for message in messages
                if message.run_id == run.id and message.role == "assistant"
            ]

            for message in assistant_messages_for_run:
                full_response = process_message_with_citations(message_with_citations=message)
                st.session_state.messages.append(
                    {"role": "assistant", "content": full_response}
                )
                with st.chat_message("assistant"):
                    st.markdown(full_response, unsafe_allow_html=True)
    else:
        st.write(
            "Please upload at least a file to get started by clicking on the 'Start Chat' button"
        )
