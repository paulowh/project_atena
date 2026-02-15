import os
import sys
import subprocess
from faster_whisper import WhisperModel

# --- TRUQUE PARA CORRIGIR O ERRO DE DLL NO WINDOWS ---
if sys.platform == "win32":
    # Procura as pastas de bibliotecas nvidia dentro do seu venv
    venv_lib = os.path.join(sys.prefix, "Lib", "site-packages")
    nvidia_dirs = [
        os.path.join(venv_lib, "nvidia", "cublas", "bin"),
        os.path.join(venv_lib, "nvidia", "cudnn", "bin")
    ]
    for folder in nvidia_dirs:
        if os.path.exists(folder):
            # Adiciona ao PATH do processo atual
            os.environ["PATH"] = folder + os.pathsep + os.environ["PATH"]
            # Para Python 3.8+, precisa usar add_dll_directory também
            try:
                os.add_dll_directory(folder)
            except AttributeError:
                pass
# ---------------------------------------------------

def extract_audio(video_path):
    audio_temp = "temp_audio_16k.wav"
    video_abs = os.path.abspath(video_path)
    audio_abs = os.path.abspath(audio_temp)
    print(f"🛠️  [PROCESSANDO] Extraindo áudio otimizado... ", end="", flush=True)
    command = ["ffmpeg", "-i", video_abs, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-y", audio_abs]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ PRONTO")
    return audio_abs

def format_time_simple(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def transcribe(video_path, output_txt, model_size="small"):
    audio_file = extract_audio(video_path)
    
    try:
        model = WhisperModel(model_size, device="cuda", compute_type="float16")
        device_label = "GPU (CUDA)"
    except Exception as e:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        device_label = f"CPU (Falha CUDA: {str(e)[:30]}...)"

    print(f"🧠 [IA] Whisper ({model_size.upper()}) pronto na {device_label}.".ljust(80))
    print(f"🎙️  [TRANSCREVENDO] Processando áudio:")
    
    segments, info = model.transcribe(audio_file, language="pt", vad_filter=True)
    total_duration = info.duration

    with open(output_txt, "w", encoding="utf-8") as f:
        for s in segments:
            percent = (s.start / total_duration) * 100
            bar_size = 20
            filled_size = int(bar_size * s.start // total_duration)
            bar = "█" * filled_size + "░" * (bar_size - filled_size)
            
            display_text = (s.text[:50] + '..') if len(s.text) > 50 else s.text
            timestamp = format_time_simple(s.start)
            
            output = f"   {bar} {percent:5.1f}% | ➔ [{timestamp}] {display_text.ljust(55)}"
            print(output, end="\r", flush=True)
            f.write(f"[{s.start:.2f} -> {s.end:.2f}] {s.text}\n")

    print(f"   {'█' * 20} 100.0% | ➔ Finalizado!{' ' * 60}\n")
    
    # Remove arquivo de áudio temporário
    if os.path.exists(audio_file):
        os.remove(audio_file)
    
    # IMPORTANTE: Ao ser chamado via wrapper, sai diretamente sem return
    # Isso evita o crash de cleanup do CUDA
    if os.environ.get('TRANSCRIBE_WRAPPER_MODE'):
        os._exit(0)
    
    return