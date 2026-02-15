import requests
import json
import re
import time
import os

def extract_json_from_response(response_text):
    """
    Limpa a resposta da LLM e garante que retorne uma lista de clips.
    """
    # 1. Tenta encontrar o conteúdo entre colchetes [ ] ou chaves { }
    # Isso ajuda se a LLM ignorou o modo JSON ou adicionou texto extra.
    match = re.search(r'(\[.*\]|\{.*\})', response_text, re.DOTALL)
    if match:
        clean_text = match.group(1)
    else:
        clean_text = response_text

    try:
        data = json.loads(clean_text)
        
        # Se o modelo retornou {"clips": [...]}, extraímos a lista
        if isinstance(data, dict):
            for key in ["clips", "cuts", "segments", "data"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data] # Se for um objeto único, envelopa em lista
            
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print(f"[ERRO] Falha ao decodificar JSON: {response_text[:100]}...")
        return []

def generate_clip_json(transcript_text, ollama_url, model_name):
    """
    Envia um trecho de transcrição para a LLM e retorna JSON de cortes.
    """
    system_prompt = (
        "Aja como um editor de Shorts/Reels. Analise a transcrição e extraia os momentos mais impactantes. Cada momento deve ter mais que 30 segundos e menos que 120 segundos. "
        "Siga o formato JSON estritamente: [{\"title\": \"...\", \"start\": 0.0, \"end\": 0.0, \"reason\": \"...\"}]"
    )

    payload = {
        "model": model_name,
        "prompt": f"TRANSCRICAO:\n{transcript_text}\n\nRetorne os cortes em JSON:",
        "system": system_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.3,
            "num_ctx": 8192
        }
    }

    try:
        response = requests.post(ollama_url, json=payload, timeout=120)
        if response.status_code == 200:
            raw_response = response.json().get("response", "")
            return extract_json_from_response(raw_response)
        else:
            print(f"Erro no Ollama: {response.status_code}")
            return []
    except Exception as e:
        print(f"Erro na requisição: {e}")
        return []
