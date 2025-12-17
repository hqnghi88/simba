import json

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from simba.chatbot.demo.graph import graph
from simba.chatbot.demo.state import State, for_client

chat = APIRouter(prefix="/chat", tags=["chat"])


# request input format
class Query(BaseModel):
    message: str
    thread_id: str = None


@chat.post("/")
async def invoke_graph(query: Query = Body(...)):
    """Invoke the graph workflow with a message"""

    import uuid

    # Use client provided thread_id or generate one if missing
    if query.thread_id:
        thread_id = query.thread_id
    else:
        # Fallback to random ID if no session provided (stateless)
        thread_id = str(uuid.uuid4())
    
    print(f"Using thread_id: {thread_id}")
    config = {"configurable": {"thread_id": thread_id}}
    state = State()
    state["messages"] = [HumanMessage(content=query.message)]

    # Helper function to check if string is numeric (including . and ,)
    def is_numeric(s):
        import re

        return bool(re.match(r"^[\d ]+$", s.strip()))

    async def generate_response():
        try:
            buffer = ""
            last_state = None
            has_sent_content = False

            async for event in graph.astream_events(state, version="v2", config=config):
                event.get("metadata", {})
                event_type = event.get("event")

                # Handle retriever node completion
                if event_type == "on_chain_end" and event["name"] == "retrieve":
                    # Store documents from node output
                    state["documents"] = event["data"]["output"]["documents"]
                    last_state = for_client(state)
                    yield f"{json.dumps({'state': last_state})}\n\n"
                if event_type == "on_chat_model_stream":
                    has_sent_content = True
                    chunk = event["data"]["chunk"].content
                    state_snapshot = for_client(state)
                    last_state = state_snapshot  # Keep track of latest state

                    # Buffer numeric chunks logic
                    if is_numeric(chunk) or (buffer and chunk in [" ", ",", "."]):
                        buffer += chunk
                    else:
                        if buffer:
                            combined = buffer + chunk
                            yield f"{json.dumps({'content': combined, 'state': last_state})}\n\n"
                            buffer = ""
                        else:
                            yield f"{json.dumps({'content': chunk, 'state': last_state})}\n\n"

                # Send state updates even when no content chunk
                elif event_type == "on_chat_end":
                    # Send the latest state that now includes documents
                    yield f"{json.dumps({'state': last_state})}\n\n"
            
            # If no content was streamed, send a fallback message
            if not has_sent_content:
                print("WARNING: No content was streamed, sending fallback response")
                yield f"{json.dumps({'content': 'I apologize, but I encountered an issue generating a response. Please try again or upload some documents to the knowledge base first.', 'state': for_client(state)})}\n\n"

        except Exception as e:
            print(f"ERROR in chat stream: {e}")
            import traceback
            traceback.print_exc()
            yield f"{json.dumps({'error': str(e)})}\n\n"
        finally:
            print("Done")

    return StreamingResponse(generate_response(), media_type="text/event-stream")


@chat.get("/status")
async def health():
    """Check the api is running"""
    return {"status": "🤙"}
