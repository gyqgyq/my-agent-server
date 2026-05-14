from fastapi import APIRouter

from langchain.agents import create_agent





router = APIRouter(prefix="/agent", tags=["agent"])

# def get_weather(city: str) -> str:
#     """Get weather for a given city."""
#     return f"It's always sunny in {city}!"

# agent = create_agent(
#     model="google_genai:gemini-2.5-flash-lite",
#     tools=[get_weather],
#     system_prompt="You are a helpful assistant",
# )

# @router.get("/get_msg")
# def get_msg(msg: str):
#     return agent.invoke({
#         "messages": [
#             {"role": "user", "content": msg}
#         ]
#     })
