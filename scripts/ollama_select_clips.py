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
        "Aja como um editor de Shorts/Reels. Analise a transcrição e extraia os momentos mais impactantes. "
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

def process_transcript_to_llm(file_path, ollama_url, model_name):
    """
    Lê o arquivo TXT de 4h, divide em blocos e manda para a LLM.
    """
    if not os.path.exists(file_path):
        print(f"Arquivo não encontrado: {file_path}")
        return

    # Lendo todas as linhas do arquivo gerado pelo Whisper
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    all_clips = []
    # Definindo tamanho do bloco (aprox. 250 linhas = ~15-20 min de vídeo)
    chunk_size = 250 

    print(f"Total de linhas: {len(lines)}. Processando em blocos de {chunk_size}...")

    for i in range(0, len(lines), chunk_size):
        chunk_text = "".join(lines[i:i + chunk_size])
        print(f">> Enviando bloco {(i//chunk_size)+1} para a LLM...")

        system_prompt = (
            "Aja como um editor de Shorts/Reels. Analise a transcrição e extraia os momentos mais impactantes. "
            "Siga o formato JSON estritamente: [{\"title\": \"...\", \"start\": 0.0, \"end\": 0.0, \"reason\": \"...\"}]"
        )

        payload = {
            "model": model_name,
            "prompt": f"TRANSCRICAO:\n{chunk_text}\n\nRetorne os cortes em JSON:",
            "system": system_prompt,
            "stream": False,
            "format": "json", # Força o Ollama a usar modo JSON
            "options": {
                "temperature": 0.3,
                "num_ctx": 8192 # Janela de contexto maior para não cortar o texto
            }
        }

        try:
            response = requests.post(ollama_url, json=payload, timeout=120)
            if response.status_code == 200:
                raw_response = response.json().get("response", "")
                clips = extract_json_from_response(raw_response)
                
                # Validação rápida de integridade dos dados
                for clip in clips:
                    if "start" in clip and "end" in clip:
                        all_clips.append(clip)
            else:
                print(f"Erro no Ollama: {response.status_code}")
        except Exception as e:
            print(f"Erro na requisição: {e}")

    # Salvando o resultado final
    with open("sugestoes_cortes.json", "w", encoding="utf-8") as f:
        json.dump(all_clips, f, indent=4, ensure_ascii=False)
    
    print(f"\n--- FIM! {len(all_clips)} clips sugeridos salvos em 'sugestoes_cortes.json' ---")

# Para rodar apenas este módulo:
if __name__ == "__main__":
    # Altere para o caminho do seu arquivo .txt real
    process_transcript_to_llm("output/transcript.txt", "http://localhost:11434/api/generate", "llama3")