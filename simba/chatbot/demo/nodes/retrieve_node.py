from simba.retrieval import Retriever

retriever = Retriever()


def retrieve(state):
    """
    Retrieve documents

    Args:
        state (dict): The current graph state

    Returns:
        state (dict): New key added to state, documents, that contains retrieved documents
    """
    try:
        print("---RETRIEVE---")
        # Use transformed query if available (handles context/history rewrite)
        if state.get("sub_queries") and len(state["sub_queries"]) > 0:
            question = state["sub_queries"][0]
            print(f"Using transformed query: {question}")
        else:
            question = state["messages"][-1].content
            print(f"Using raw question: {question}")
            
        # Retrieval with error handling
        documents = retriever.retrieve(question, method="default")
        print(f"Retrieved {len(documents)} documents")

        return {"documents": documents, "question": question}
    except KeyError as e:
        print(f"Error retrieving documents: {e}")
        # Return empty documents list if retrieval fails
        return {"documents": [], "question": question}
