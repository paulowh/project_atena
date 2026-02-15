"""
Wrapper para executar transcrição em processo separado
Evita crash de CUDA cleanup
"""
import sys
import os

# Adiciona o diretório raiz do projeto ao path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Seta flag para modo wrapper (evita crash CUDA no return)
os.environ['TRANSCRIBE_WRAPPER_MODE'] = '1'

from scripts.transcribe import transcribe

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: transcribe_wrapper.py <video_path> <output_txt> <model_size>")
        os._exit(1)
    
    video_path = sys.argv[1]
    output_txt = sys.argv[2]
    model_size = sys.argv[3]
    
    try:
        transcribe(video_path, output_txt, model_size)
        os._exit(0)
    except Exception as e:
        print(f"Erro na transcrição: {e}")
        import traceback
        traceback.print_exc()
        os._exit(1)
