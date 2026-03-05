import os
import sys
import json
import subprocess
from scripts.ollama_select_clips import generate_clip_json
from scripts.cut_clips import cut_multiple_clips
from scripts.emotion_analyzer import get_emotional_segments
from scripts.vision_analyzer import analyze_frame_with_llava

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b" 

def main(video_path: str):
    if not os.path.exists(video_path):
        print(f"❌ Erro: Arquivo '{video_path}' não encontrado.")
        return

    base_name = os.path.splitext(os.path.basename(video_path))[0]
    os.makedirs("output", exist_ok=True)
    os.makedirs("output/clips", exist_ok=True)

    transcript_path = os.path.join("output", f"{base_name}-transcript.txt")
    clips_json_path = os.path.join("output", f"{base_name}-clips.json")
    clips_output_folder = os.path.join("output", "clips", base_name)

    print("\n" + "="*50)
    print(f"ATENA VIDEO PROCESSOR - {base_name.upper()}")
    print("="*50)
    print("0 - PROCESSO COMPLETO (Transcrição -> IA -> Cortes)")
    print("-" * 50)
    print("1 - Apenas Transcrever Vídeo")
    print("2 - Apenas Gerar Sugestões (JSON) via IA")
    print("3 - Apenas Cortar Vídeo (Baseado no JSON)")
    print("4 - [NOVO] IA MULTIMODAL (Análise de Emoção + Visão)")
    print("="*50)
    
    choice = input("Escolha o que deseja fazer: ").strip()

    # --- 1. ETAPA DE TRANSCRIÇÃO ---
    if choice in ["0", "1"]:
        print("\n[1/3] INICIANDO TRANSCRIÇÃO...")
        
        # Executa transcrição em processo separado para evitar crash CUDA
        # O wrapper transcribe_wrapper.py cuida de chamar a função de transcrição e sair sem retornar
        wrapper_path = os.path.join("scripts", "transcribe_wrapper.py")
        try:
            result = subprocess.run(
                [sys.executable, wrapper_path, video_path, transcript_path, "small"],
                check=True,
                capture_output=False
            )
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Erro na transcrição (código {e.returncode})")
            return
        except Exception as e:
            print(f"\n❌ Erro ao executar transcrição: {e}")
            return
        
        print(f"✅ Transcrição salva em: {os.path.basename(transcript_path)}")
        
        if choice == "1": 
            print("\n✅ Processo concluído.")
            return

    # --- 2. ETAPA DE IA (OLLAMA) ---
    if choice in ["0", "2"]:
        if not os.path.exists(transcript_path):
            print(f"\n❌ Erro: Transcrição não encontrada")
            return

        print("\n[2/3] ANALISANDO TRANSCRIÇÃO COM IA...")
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        all_clips = []
        chunk_size = 250 
        total_chunks = (len(lines) // chunk_size) + 1
        
        print(f"🤖 Modelo: {OLLAMA_MODEL}")
        for i in range(0, len(lines), chunk_size):
            chunk_text = "".join(lines[i:i + chunk_size])
            current_chunk = (i // chunk_size) + 1
            
            # Barra de progresso similar ao transcribe
            percent = (current_chunk / total_chunks) * 100
            bar_size = 20
            filled = int(bar_size * current_chunk / total_chunks)
            bar = "█" * filled + "░" * (bar_size - filled)
            
            print(f"   {bar} {percent:5.1f}% | Analisando bloco {current_chunk}/{total_chunks}", end="\r", flush=True)
            
            try:
                clips = generate_clip_json(chunk_text, OLLAMA_URL, OLLAMA_MODEL)
                if clips:
                    all_clips.extend(clips)
            except Exception as e:
                print(f"\n   ⚠️ Erro no bloco {current_chunk}: {e}")

        print(f"\n   {'█' * 20} 100.0% | Análise concluída!{' ' * 30}")
        
        if not all_clips:
            print("\n❌ A IA não gerou cortes. Verifique se o Ollama está rodando.")
            return

        # Salva o JSON
        with open(clips_json_path, "w", encoding="utf-8") as f:
            json.dump(all_clips, f, indent=2, ensure_ascii=False)
        print(f"✅ {len(all_clips)} cortes salvos em: {os.path.basename(clips_json_path)}")
        
        if choice == "2": 
            print("\n✅ Processo concluído.")
            return

    # --- 3. ETAPA DE CORTE (FFMPEG) ---
    if choice in ["0", "3"]:
        if not os.path.exists(clips_json_path):
            print(f"\n❌ Erro: JSON de cortes não encontrado.")
            return
        
        with open(clips_json_path, "r", encoding="utf-8") as f:
            clips_to_cut = json.load(f)

        print(f"\n[3/3] GERANDO REELS...")
        
        # Verifica se há transcrição disponível para legendas
        if os.path.exists(transcript_path):
            print(f"✅ Transcrição encontrada - Legendas serão incluídas")
        else:
            print(f"⚠️  Transcrição não encontrada - Gerando sem legendas")
            
        try:
            cut_multiple_clips(video_path, clips_to_cut, clips_output_folder, transcript_path)
        except Exception as e:
            print(f"\n❌ Erro no FFmpeg: {e}")

    if choice == "4":
        # PASSO 1: Achar picos de áudio
        peaks = get_emotional_segments(video_path)
        print(f"✨ Encontrados {len(peaks)} momentos candidatos.")
        
        all_clips = []
        for i, timestamp in enumerate(peaks):
            print(f"📸 Analisando visualmente o momento {i+1}/{len(peaks)}...")
            
            # PASSO 2: IA "Vê" o frame
            desc = analyze_frame_with_llava(video_path, timestamp, 
                "Descreva o que acontece nesta cena de jogo. É um momento de ação, vitória ou algo engraçado?")
            
            # Aqui você pode salvar no formato JSON que seu cut_clips já entende
            all_clips.append({
                "title": f"Destaque {i+1}",
                "start": max(0, timestamp - 15), # 15s antes do pico
                "end": timestamp + 20,           # 20s depois do pico
                "reason": desc
            })
            
        # Agora só chamar sua função de corte que já está pronta!
        cut_multiple_clips(video_path, all_clips, clips_output_folder)

        
    print(f"\n📂 Arquivos em: {os.path.abspath(clips_output_folder)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python main.py <caminho_do_video>")
    else:
        main(sys.argv[1])