from fastapi import FastAPI
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from agent.agent import agent_respond, agent_respond_stream
from fastapi.responses import StreamingResponse
import uvicorn
import json

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    message: str
    options: dict = {}

@app.post("/chat")
async def chat(query: Query):
    result = agent_respond(query.message, options=query.options)
    return {"result": result}


@app.post("/chat/stream")
async def chat_stream(query: Query):
    deep_thinking = query.options.get("deep_thinking", False)
    def event_stream():
        for entry in agent_respond_stream(query.message, deep_thinking=deep_thinking):
            # 实时打印最终回复内容到后端终端
            if entry.get("type") == "chat":
                print(f'[CHATBOT] {entry.get("content")}', flush=True)
            # SSE协议格式，每个消息前加"data: "，后加两个\n
            yield f"data: {json.dumps(entry, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/stream")
def stream():
    import time
    def event_stream():
        for i in range(10):
            yield f"data: 第{i+1}条消息\n\n"
            time.sleep(2)
    return StreamingResponse(event_stream(), media_type="text/event-stream")

# if __name__ == "__main__":
#    uvicorn.run("main:app", port=8000, reload=True)
