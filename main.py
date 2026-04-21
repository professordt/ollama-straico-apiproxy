import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from aio_straico import straico_client
import uvicorn

app = FastAPI(title="Straico Universal Agent Proxy")

STRAICO_API_KEY = os.getenv("STRAICO_API_KEY")

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    body = await request.json()
    model = body.get("model", "")
    messages = body.get("messages", [])
    # Extract the last message as the prompt
    prompt = messages[-1]["content"] if messages else ""

    try:
        with straico_client(API_KEY=STRAICO_API_KEY) as client:
            # 1. AGENT ROUTE (Format: agent:ID)
            if model.startswith("agent:"):
                agent_id = model.split(":")[1]
                response = client.agent_prompt_completion(agent_id=agent_id, prompt=prompt)
            
            # 2. RAG ROUTE (Format: rag:ID|actual_model)
            elif model.startswith("rag:"):
                parts = model.split(":")[1].split("|")
                rag_id = parts[0]
                actual_model = parts[1] if len(parts) > 1 else "openai/gpt-4o-mini"
                response = client.rag_prompt_completion(rag_id=rag_id, model=actual_model, prompt=prompt)
            
            # 3. STANDARD MODEL ROUTE
            else:
                response = client.prompt_completion(model=model, prompt=prompt)

            # Format the Straico response back to OpenAI standard
            # This is a simplified wrapper for compatibility
            content = response.get("completions", {}).get(model, {}).get("completion", {}).get("choices", [{}])[0].get("message", {}).get("content", "Error: No response")
            
            return {
                "id": "straico-proxy",
                "object": "chat.completion",
                "model": model,
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop", "index": 0}]
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # We run on 3214 internally, Docker will map it to 11444
    uvicorn.run(app, host="0.0.0.0", port=3214)