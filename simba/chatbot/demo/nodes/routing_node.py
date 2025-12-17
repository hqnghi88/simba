import logging
from simba.chatbot.demo.chains.routing_chain import routing_chain
from simba.chatbot.demo.state import State

logger = logging.getLogger(__name__)


def routing(state: State):
    question = state["messages"][-1].content
    logger.info(f"Routing question: {question}")
    # Force transform_query to ensure flow continues for all inputs during local dev
    return "transform_query"
    # route = routing_chain.invoke({"question": question})
    # return route.route