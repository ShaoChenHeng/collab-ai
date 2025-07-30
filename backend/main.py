from fastapi import FastAPI
from pydantic import BaseModel
from agent.agent import agent_respond, agent_respond_stream
from fastapi.responses import StreamingResponse
import uvicorn
import json
app = FastAPI()

class Query(BaseModel):
    message: str

@app.post("/chat")
async def chat(query: Query):
    result = agent_respond(query.message)
    return {"result": result}


@app.post("/chat/stream")
async def chat_stream(query: Query):
    def event_stream():
        for entry in agent_respond_stream(query.message):
            # SSE协议格式，每个消息前加"data: "，后加两个\n
            yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

# if __name__ == "__main__":
#    uvicorn.run("main:app", port=8000, reload=True)