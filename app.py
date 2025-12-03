import os
import re
import uuid
import boto3
import streamlit as st

# -----------------------------
# Config: region + agent details
# -----------------------------
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Make these required so you don't accidentally hit the wrong agent
AGENT_ID = os.environ["AGENT_ID"]          # e.g. SV5WQN608J
AGENT_ALIAS_ID = os.environ["AGENT_ALIAS_ID"]  # e.g. GIMUO9R1JW

bedrock_runtime = boto3.client("bedrock-agent-runtime", region_name=REGION)


def call_bedrock_agent(user_text: str, session_id: str) -> str:
    """
    Call Bedrock Agent and return text inside <answer>...</answer>.
    Fallback: return full raw output.
    """
    response = bedrock_runtime.invoke_agent(
        agentId=AGENT_ID,
        agentAliasId=AGENT_ALIAS_ID,
        sessionId=session_id,
        inputText=user_text,
    )

    chunks = []
    for event in response["completion"]:
        if "chunk" in event:
            chunks.append(event["chunk"]["bytes"].decode("utf-8"))

    full = "".join(chunks)

    m = re.search(r"<answer>(.*?)</answer>", full, re.DOTALL)
    if m:
        answer = m.group(1).strip()
    else:
        answer = full.strip()

    if len(answer) > 8000:
        answer = answer[:8000] + "\n\n…(truncated)"

    return answer or "I couldn't find an answer for that query."


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(
    page_title="DASH – Dynamic Analytics & Semantic Handling",
    layout="wide"
)

st.title("DASH – Dynamic Analytics & Semantic Handling")
st.caption("Inventory & returns analytics chatbot (Bedrock Agent + Athena)")

# Session state for chat history
if "messages" not in st.session_state:
    st.session_state["messages"] = []  # list of dicts {role, content}
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())

# Sidebar info
with st.sidebar:
    st.subheader("How to use")
    st.markdown(
        """
        Examples you can ask:
        - `Return-to-vendor data for December 2024, grouped by country`
        - `Break down Germany RTV COGS by macro_category for Dec 2024`
        - `Top 5 reason_code by COGS for UK in Dec 2024`
        """
    )
    st.markdown("---")
    st.markdown(f"**Region:** `{REGION}`")
    st.markdown(f"**Agent ID:** `{AGENT_ID}`")
    st.markdown(f"**Alias ID:** `{AGENT_ALIAS_ID}`")

# Show chat history
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**DASH:** {msg['content']}")

st.markdown("---")

user_input = st.text_input(
    "Ask DASH a question:",
    placeholder="e.g. Return-to-vendor data for December 2024, grouped by country",
)

col1, col2 = st.columns([1, 4])
with col1:
    ask_clicked = st.button("Ask DASH")

if ask_clicked and user_input.strip():
    # Add user message to history
    st.session_state["messages"].append({"role": "user", "content": user_input})

    with st.spinner("Querying Bedrock Agent (via Athena)..."):
        try:
            session_id = st.session_state["session_id"]
            answer = call_bedrock_agent(user_input, session_id=session_id)
        except Exception as e:
            answer = f"Error calling Bedrock Agent:\n\n`{repr(e)}`"

    # Add answer to history and show
    st.session_state["messages"].append({"role": "assistant", "content": answer})
    st.rerun()
