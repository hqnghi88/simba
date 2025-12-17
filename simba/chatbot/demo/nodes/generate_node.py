from langchain_core.messages import AIMessage

from simba.chatbot.demo.chains.generate_chain import generate_chain


def generate(state):
    """
    Generate answer

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, generation, that contains LLM generation
    """
    print("---GENERATE---")
    question = state["messages"][-1].content
    
    # Use compressed documents as context (fallback to original documents if compression not available)
    context_docs = state["documents"]
    print(f"Using {len(context_docs)} compressed documents for generation")
    

    # context_docs contains LangChain Document objects directly from retrieval
    docs_content = "\n\n".join(
        doc.page_content
        for doc in context_docs
        if doc and hasattr(doc, "page_content")
    )
    
    # Debug log the context size
    print(f"Context content length: {len(docs_content)} chars")

    summaries = state["summaries"]
    
    # Format chat history as a readable string
    chat_history_str = ""
    messages_list = state["messages"]

    for msg in messages_list[:-1]: # Exclude the current last message
        role = "User" if msg.type == "human" else "Simba"
        chat_history_str += f"{role}: {msg.content}\n"
    
    if not chat_history_str:
        chat_history_str = "No history."

    # RAG generation
    generation = generate_chain.invoke(
        {
            "summaries": summaries,
            "context": docs_content,
            "question": question,
            "chat_history": chat_history_str,
        }
    )

    messages = state["messages"] + [AIMessage(content=generation)]

    # Return both the compressed documents and original documents to maintain state
    return {
        "documents": state.get("documents", []),
        "compressed_documents": context_docs,
        "messages": messages, 
        "generation": generation
    }
