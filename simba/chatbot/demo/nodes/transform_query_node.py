from simba.chatbot.demo.chains.transform_query_chain import question_rewrite_chain


def transform_query(state):
    """
    Transform the query to produce a better question.
    Tracks number of attempts to prevent infinite loops.

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): Updates question key with a re-phrased question
    """ 

    print("---TRANSFORM QUERY---")
    question = state["messages"][-1].content
    
    # Track transformation attempts
    transform_attempts = state.get("transform_attempts", 0)
    transform_attempts += 1
    
    # Format chat history
    chat_history_str = ""
    for msg in state["messages"][:-1]:
        role = "User" if msg.type == "human" else "Simba"
        chat_history_str += f"{role}: {msg.content}\n"
        
    print(f"Query transformation attempt #{transform_attempts}")
    
    # Re-write question
    better_question = question_rewrite_chain.invoke({
        "question": question,
        "chat_history": chat_history_str
    })
    
    return {
        "question": question,
        "sub_queries": better_question.sub_queries,
        "transform_attempts": transform_attempts
    }