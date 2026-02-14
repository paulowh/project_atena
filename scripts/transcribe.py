import sys
import os
import subprocess
from faster_whisper import WhisperModel

def extract_audio(video_path):
    """Extrai apenas o áudio em 16kHz Mono (formato ideal para Whisper)"""
    audio_temp = "temp_audio_16k.wav"
    print("--- Extraindo e otimizando áudio (FFmpeg) ---")
    command = [
        "ffmpeg", "-i", video_path,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        "-y", audio_temp
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return audio_temp

def transcribe(video_path: str, output_txt: str, model_size="small"):
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Arquivo não encontrado: {video_path}")

    # Extrai o áudio primeiro para evitar que o Whisper decodifique o vídeo de 4h
    audio_file = extract_audio(video_path)

    # Detecta se há GPU NVIDIA disponível
    device = "cuda" if os.system("nvidia-smi > /dev/null 2>&1") == 0 else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    print(f"--- Iniciando Transcrição (Rodando em: {device.upper()}) ---")

    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # Otimizações Chave:
    # 1. vad_filter: Pula silêncios (ganho absurdo de tempo em vídeos longos)
    # 2. beam_size=1: Transcrição mais rápida (greedy decoding)
    segments, info = model.transcribe(
        audio_file, 
        language="pt", 
        vad_filter=True, 
        vad_parameters=dict(min_silence_duration_ms=500),
        beam_size=1 
    )

    with open(output_txt, "w", encoding="utf-8") as f:
        for s in segments:
            # Print de progresso no terminal para você não achar que travou
            print(f"[{s.start/3600:.2f}h] {s.text}") 
            f.write(f"[{s.start:.2f} -> {s.end:.2f}] {s.text}\n")

    # Limpeza
    if os.path.exists(audio_file):
        os.remove(audio_file)

    return output_txt

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python script.py video.mp4 output.txt")
    else:
        video_input = sys.argv[1]
        output_file = sys.argv[2]
        transcribe(video_input, output_file)
        print(f"\n✅ Concluído! Salvo em: {output_file}")