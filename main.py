import os
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from aio_straico import aio_straico_client

app = FastAPI(title="Straico Universal Agent Proxy")
STRAICO_API_KEY = os.getenv("STRAICO_API_KEY")

@app.get("/")
async def root():
    return {"status": "online", "message": "Straico Agent Proxy running on 11444"}

@app.get("/v1/models")
async def list_models():
    try:
        async with aio_straico_client(API_KEY=STRAICO_API_KEY) as client:
            all_options = []
            # Standard Models
            models_data = await client.models()
            for m_name in models_data.keys():
                all_options.append({"id": m_name, "object": "model", "owned_by": "straico"})
            # Agents
            try:
                agents = await client.agents()
                for agent in agents:
                    all_options.append({"id": f"agent:{agent['_id']}", "object": "model", "owned_by": f"agent-{agent['name']}"})
            except Exception as e:
                print(f"Error fetching agents: {e}")
            return {"object": "list", "data": all_options}
    except Exception as e:
        print(f"Error in list_models: {e}")
        return {"object": "list", "data": [{"id": "openai/gpt-4o", "object": "model"}]}

@app.post("/v1/chat/completions")
async def chat_proxy(request: Request):
    body = await request.json()
    model = body.get("model", "")
    messages = body.get("messages", [])
    prompt = messages[-1]["content"] if messages else ""

    try:
        async with aio_straico_client(API_KEY=STRAICO_API_KEY) as client:
            # AGENT ROUTE: model starts with "agent:"
            if model.startswith("agent:"):
                agent_id = model.split(":")[1]
                response = await client.agent_prompt_completion(agent_id, prompt)
                content = response["answer"] if isinstance(response, dict) else str(response)

            # RAG ROUTE: model starts with "rag:"
            elif model.startswith("rag:"):
                parts = model.replace("rag:", "").split("|")
                rag_id = parts[0]
                actual_model = parts[1] if len(parts) > 1 else "openai/gpt-4o"
                response = await client.rag_prompt_completion(rag_id, actual_model, prompt)
                content = response.get("answer", response.get("completion", {}).get("choices", [{}])[0].get("message", {}).get("content", str(response)))

            # STANDARD ROUTE: normal model
            else:
                response = await client.prompt_completion(model, prompt)
                # Handle different response structures
                if isinstance(response, dict):
                    # Try standard completion structure
                    if "completion" in response:
                        content = response["completion"].get("choices", [{}])[0].get("message", {}).get("content", str(response))
                    # Try nested completions structure
                    elif "completions" in response:
                        model_key = list(response["completions"].keys())[0]
                        content = response["completions"][model_key]["completion"]["choices"][0]["message"]["content"]
                    else:
                        content = str(response)
                else:
                    content = str(response)

            return {
                "id": "straico-proxy",
                "object": "chat.completion",
                "model": model,
                "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop", "index": 0}]
            }
    except Exception as e:
        print(f"Error in chat_proxy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3214)
