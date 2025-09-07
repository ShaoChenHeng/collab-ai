from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from agent.agent import agent_respond, agent_respond_stream
from fastapi.responses import StreamingResponse
import uvicorn
import os
import time
from pathlib import Path
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from agent.tools.docs.docs_tool import WORKSPACE_ROOT

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

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 仅允许 txt 与 pdf
    ext = Path(file.filename).suffix.lower()
    if ext not in {".txt", ".pdf"}:
        raise HTTPException(status_code=400, detail="仅支持 txt 或 pdf 文件")

    # 清理文件名，防止路径穿越
    clean_name = Path(file.filename).name
    dest_dir = Path(WORKSPACE_ROOT)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / clean_name

    # 若同名文件已存在，追加时间戳避免覆盖
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        clean_name = f"{stem}_{int(time.time())}{suffix}"
        dest_path = dest_dir / clean_name

    # 流式写入，避免占用过多内存
    with open(dest_path, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    rel_path = str(Path(clean_name))  # 相对 workspace 的路径
    return {"ok": True, "filename": clean_name, "path": rel_path}

# if __name__ == "__main__":
#    uvicorn.run("main:app", port=8000, reload=True)
