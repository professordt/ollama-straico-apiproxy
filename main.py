import os
from fastapi import FastAPI, Request, HTTPException
from aio_straico import straico_client
import uvicorn

app = FastAPI()
STRAICO_API_KEY = os.getenv("STRAICO_API_KEY")

@app.get("/")
async def root():
    return {"message": "Agent Proxy Active on 11444"}

# 1. This tells your app which Agents you have
@app.get("/v1/models")
async def list_models():
    try:
        with straico_client(API_KEY=STRAICO_API_KEY) as client:
            all_models = []
            
            # Fetch Standard LLMs
            models = client.models()
            for m in models.keys():
                all_models.append({"id": m, "object": "model", "owned_by": "straico"})
            
            # Fetch your Custom Agents (v0)
            agents = client.agents()
            for a in agents:
                # We prefix with 'agent:' so the proxy knows it's an agent
                all_models.append({
                    "id": f"agent:{a['_id']}", 
                    "object": "model", 
                    "owned_by": f"straico-agent-{a['name']}"
                })
            
            return {"object": "list", "data": all_models}
    except Exception as e:
        return {"object": "list", "data": [{"id": "openai/gpt-4o", "object": "model"}]}

# 2. This handles the actual chatting
@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    model = body.get("model", "")
    messages = body.get("messages", [])
    prompt = messages[-1]["content"] if messages else ""

    try:
        with straico_client(API_KEY=STRAICO_API_KEY) as client:
            # --- AGENT LOGIC ---
            if model.startswith("agent:"):
                agent_id = model.split(":")[1]
                # Use the specific Agent Completion method
                response = client.agent_prompt_completion(agent_id=agent_id, prompt=prompt)
                # Agents return the answer in a specific 'completion' field
                content = response['completion']['choices'][0]['message']['content']
            
            # --- STANDARD MODEL LOGIC ---
            else:
                response = client.prompt_completion(model=model, prompt=prompt)
                # Standard models return answers nested by model name
                model_key = list(response['completions'].keys())[0]
                content = response['completions'][model_key]['completion']['choices'][0]['message']['content']

            return {
                "id": "straico-resp",
                "object": "chat.completion",
                "model": model,
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop", "index": 0}]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3214)