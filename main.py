import os
import sys
import json
from scripts.transcribe import transcribe
from scripts.ollama_select_clips import generate_clip_json
from scripts.cut_clips import cut_multiple_clips

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b" 

def main(video_path: str):
    if not os.path.exists(video_path):
        print(f"❌ Erro: O arquivo de vídeo '{video_path}' não foi encontrado.")
        return

    os.makedirs("output", exist_ok=True)
    os.makedirs("output/clips", exist_ok=True)

    transcript_path = "output/transcript.txt"
    clips_json_path = "output/clips.json"

    # --- MENU ---
    print("\n📌 MENU DE OPÇÕES")
    print("1 - Gerar transcrição completa e sugerir cortes (Processo Completo)")
    print("2 - Usar transcrição existente para sugerir novos cortes (LLM)")
    print("3 - Apenas cortar o vídeo usando o clips.json existente")
    choice = input("Escolha uma opção (1, 2 ou 3): ").strip()

    # --- LÓGICA DE EXECUÇÃO ---
    
    # Caso 3: Pula direto para o corte
    if choice == "3":
        if not os.path.exists(clips_json_path):
            print("❌ Erro: clips.json não encontrado em 'output/'.")
            return
        with open(clips_json_path, "r", encoding="utf-8") as f:
            all_clips = json.load(f)
        print("✅ Usando dados do clips.json existente.")

    # Caso 1 e 2: Precisam processar a LLM
    elif choice in ["1", "2"]:
        if choice == "1":
            print("[1/4] Transcrevendo vídeo (isso pode demorar)...")
            transcribe(video_path, transcript_path, model_size="small")
            print("✅ Transcrição finalizada!")
        else:
            if not os.path.exists(transcript_path):
                print("❌ Erro: transcript.txt não encontrado. Use a opção 1 primeiro.")
                return
            print("[1/4] Usando transcrição existente...")

        # Processamento com Ollama (Compartilhado entre opção 1 e 2)
        print("[2/4] Lendo transcrição...")
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        all_clips = []
        chunk_size = 250 
        total_chunks = (len(lines) // chunk_size) + 1
        
        print(f"[3/4] Enviando para Ollama ({OLLAMA_MODEL}) em {total_chunks} blocos...")
        for i in range(0, len(lines), chunk_size):
            chunk_text = "".join(lines[i:i + chunk_size])
            current_chunk = (i // chunk_size) + 1
            print(f"   -> Analisando bloco {current_chunk}/{total_chunks}...")
            
            try:
                clips = generate_clip_json(chunk_text, OLLAMA_URL, OLLAMA_MODEL)
                if clips:
                    all_clips.extend(clips)
            except Exception as e:
                print(f"   ⚠️ Erro no bloco {current_chunk}: {e}")

        if not all_clips:
            print("❌ A LLM não gerou nenhum clipe válido.")
            return

        # Salva o JSON gerado
        print("[+] Salvando novas sugestões em clips.json...")
        with open(clips_json_path, "w", encoding="utf-8") as f:
            json.dump(all_clips, f, indent=2, ensure_ascii=False)
    
    else:
        print("❌ Opção inválida!")
        return

    # --- ETAPA FINAL: CORTE (Executada por todas as opções válidas) ---
    print(f"\n[4/4] Iniciando corte de {len(all_clips)} clips...")
    try:
        cut_multiple_clips(video_path, all_clips, "output/clips")
        print("\n✨ PROCESSO CONCLUÍDO COM SUCESSO!")
    except Exception as e:
        print(f"❌ Erro crítico ao cortar vídeo: {e}")

    print(f"📂 Pasta de saída: {os.path.abspath('output/clips')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python main.py <caminho_do_video>")
    else:
        main(sys.argv[1])