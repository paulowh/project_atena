import os
import subprocess
from tqdm import tqdm


def format_time(seconds: float):
    """Converte segundos para HH:MM:SS"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"


def run_ffmpeg_with_progress(cmd, duration):
    """
    Executa ffmpeg e mostra barra real com base no out_time_ms.
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
    except FileNotFoundError:
        print("\n❌ ERRO CRÍTICO: O FFmpeg não foi encontrado no sistema.")
        print("👉 Instale o FFmpeg para continuar (comando: 'winget install Gyan.FFmpeg') e reinicie o terminal.")
        raise RuntimeError("FFmpeg não encontrado.")

    pbar = tqdm(total=duration, unit="s", ncols=90)

    current_time = 0.0
    last_lines = []

    while True:
        line = process.stdout.readline()

        if not line:
            break

        last_lines.append(line)
        if len(last_lines) > 30:
            last_lines.pop(0)

        line = line.strip()

        if line.startswith("out_time_ms="):
            out_time_ms = int(line.split("=")[1])
            out_time_sec = out_time_ms / 1_000_000

            # Atualiza barra só com diferença
            delta = out_time_sec - current_time
            if delta > 0:
                pbar.update(delta)
                current_time = out_time_sec

                pbar.set_postfix_str(
                    f"{format_time(current_time)} / {format_time(duration)}"
                )

        if line.startswith("progress=") and "end" in line:
            break

    process.wait()
    pbar.close()

    if process.returncode != 0:
        error_log = "".join(last_lines)
        raise RuntimeError(f"Erro no ffmpeg:\n{error_log}")


def cut_multiple_clips(video_path, raw_clips_data, output_folder):
    """
    Corta vários clips do vídeo lidando com a estrutura aninhada da LLM.
    """
    os.makedirs(output_folder, exist_ok=True)

    # --- NOVO: Lógica de Extração de Clips ---
    # Como a LLM mandou [{"transcricao": [...]}, {"transcrição": [...]}]
    # precisamos "achatar" essa lista para uma lista simples de dicionários.
    all_flattened_clips = []
    
    for item in raw_clips_data:
        # Se for um dicionário que contém uma lista dentro (ex: chave 'transcricao')
        if isinstance(item, dict):
            # Procura por qualquer chave que contenha a lista de clips
            found_list = False
            for key in ["transcricao", "transcrição", "clips", "segments"]:
                if key in item and isinstance(item[key], list):
                    all_flattened_clips.extend(item[key])
                    found_list = True
                    break
            
            # Se não achou as chaves acima mas o item em si tem start/end
            if not found_list and "start" in item:
                all_flattened_clips.append(item)
        elif isinstance(item, list):
            all_flattened_clips.extend(item)

    if not all_flattened_clips:
        print("⚠️ Aviso: Nenhum clipe válido encontrado para processar.")
        return

    # --- FIM DA LÓGICA DE EXTRAÇÃO ---

    for i, clip in enumerate(all_flattened_clips, start=1):
        try:
            title = clip.get("title", f"clip_{i}")
            start = float(clip["start"])
            end = float(clip["end"])
            duration = end - start

            if duration <= 0:
                print(f"⚠️ Ignorando clip {i}: Duração inválida ({duration}s)")
                continue

            # Limpa caracteres inválidos
            safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title).strip()
            safe_title = safe_title[:50]
            output_path = os.path.join(output_folder, f"{i:02d}_{safe_title}.mp4")

            print(f"\n🎬 Gerando clip {i}/{len(all_flattened_clips)}: {safe_title}")
            print(f"⏱️ {format_time(start)} -> {format_time(end)} (duração: {int(duration)}s)")

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-progress", "pipe:1",
                "-nostats",
                output_path
            ]

            run_ffmpeg_with_progress(cmd, duration)
            print(f"✅ Clip salvo em: {output_path}")

        except KeyError as e:
            print(f"❌ Erro no formato do clip {i}: Faltando chave {e}. Dados: {clip}")
            continue
        except Exception as e:
            print(f"❌ Erro inesperado no clip {i}: {e}")
            continue