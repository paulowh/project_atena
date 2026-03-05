import os
import subprocess
import json
import re
from tqdm import tqdm

def format_time(seconds: float):
    """Converte segundos para HH:MM:SS fixo"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

def format_srt_time(seconds: float):
    """Converte segundos para formato SRT: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def parse_transcript(transcript_path):
    """Lê o arquivo de transcrição e retorna lista de segmentos"""
    segments = []
    if not os.path.exists(transcript_path):
        print(f"❌ Arquivo de transcrição não encontrado: {transcript_path}")
        return segments
    
    with open(transcript_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Formato: [0.00 -> 2.24]  Texto da legenda
            # Aceita números com ou sem decimais
            match = re.match(r'\[(\d+\.?\d*) -> (\d+\.?\d*)\]\s+(.+)', line.strip())
            if match:
                start = float(match.group(1))
                end = float(match.group(2))
                text = match.group(3).strip()
                segments.append({'start': start, 'end': end, 'text': text})
    
    print(f"📝 Parser: {len(segments)} segmentos extraídos de {transcript_path}")
    return segments

def create_srt_for_clip(segments, clip_start, clip_end, srt_path):
    """Cria arquivo SRT para um clip específico com timestamps ajustados"""
    # Filtra segmentos que estão dentro do intervalo do clip
    clip_segments = []
    for seg in segments:
        # Verifica se o segmento tem alguma sobreposição com o clip
        if seg['end'] > clip_start and seg['start'] < clip_end:
            # Ajusta timestamps relativos ao início do clip
            new_start = max(0, seg['start'] - clip_start)
            new_end = min(clip_end - clip_start, seg['end'] - clip_start)
            clip_segments.append({
                'start': new_start,
                'end': new_end,
                'text': seg['text']
            })
    
    if len(clip_segments) == 0:
        print(f"   ⚠️  Nenhuma legenda neste intervalo ({clip_start:.2f}s - {clip_end:.2f}s)")
        return False
    
    # Gera arquivo SRT
    with open(srt_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(clip_segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n")
            f.write(f"{seg['text']}\n")
            f.write("\n")
    
    print(f"   📝 {len(clip_segments)} legendas adicionadas")
    return True

def run_ffmpeg_with_progress(cmd, duration):
    """
    Executa ffmpeg com interface estática e números truncados.
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
        print("\n❌ ERRO CRÍTICO: FFmpeg não encontrado.")
        raise RuntimeError("FFmpeg não encontrado.")

    # Arredondamos a duração total para 2 casas
    duration = round(float(duration), 2)

    # bar_format customizado: 
    # {n:2.2f} força o número atual a ter 2 casas decimais e espaço fixo
    # {total:2.2f} força o total a ter 2 casas decimais
    pbar = tqdm(
        total=duration, 
        unit="s", 
        ncols=100, # Largura fixa para evitar quebra de linha
        bar_format='{l_bar}{bar}| {n:2.2f}/{total:2.2f}s [{elapsed}<{remaining}] {postfix}'
    )

    current_time = 0.0
    last_lines = []

    while True:
        line = process.stdout.readline()
        if not line:
            break

        last_lines.append(line)
        if len(last_lines) > 30: last_lines.pop(0)

        line = line.strip()
        if line.startswith("out_time_ms="):
            time_value = line.split("=")[1]
            # Ignora se FFmpeg retornar 'N/A'
            if time_value == "N/A":
                continue
            
            try:
                out_time_ms = int(time_value)
                out_time_sec = round(out_time_ms / 1_000_000, 2)

                delta = out_time_sec - current_time
                if delta > 0:
                    pbar.update(delta)
                    current_time = out_time_sec

                    # Postfix com largura fixa para o tempo formatado
                    pbar.set_postfix_str(
                        f"{format_time(current_time)} / {format_time(duration)}",
                        refresh=True
                    )
            except ValueError:
                # Ignora valores inválidos
                continue

        if line.startswith("progress=") and "end" in line:
            break

    process.wait()
    pbar.close()

    if process.returncode != 0:
        error_log = "".join(last_lines)
        raise RuntimeError(f"Erro no ffmpeg:\n{error_log}")

def cut_multiple_clips(video_path, raw_clips_data, output_folder, transcript_path=None):
    """
    Corta clips com interface de terminal ultra-limpa e simétrica.
    Adiciona legendas queimadas se transcript_path for fornecido.
    """
    os.makedirs(output_folder, exist_ok=True)
    
    # Carrega transcrição se disponível
    transcript_segments = []
    if transcript_path and os.path.exists(transcript_path):
        transcript_segments = parse_transcript(transcript_path)
        print(f"📝 Legendas carregadas: {len(transcript_segments)} segmentos")
    else:
        if transcript_path:
            print(f"⚠️  Arquivo de transcrição não encontrado: {transcript_path}")
        print(f"ℹ️  Gerando vídeos SEM legendas")

    # Extração de clips (Flattening)
    all_flattened_clips = []
    for item in raw_clips_data:
        if isinstance(item, dict):
            for key in ["transcricao", "transcrição", "clips", "segments"]:
                if key in item and isinstance(item[key], list):
                    all_flattened_clips.extend(item[key])
                    break
            if "start" in item and "end" in item:
                all_flattened_clips.append(item)
        elif isinstance(item, list):
            all_flattened_clips.extend(item)

    if not all_flattened_clips:
        print("⚠️ Nenhum clipe válido.")
        return

    success_count = 0
    error_count = 0

    for i, clip in enumerate(all_flattened_clips, start=1):
        try:
            title = clip.get("title", f"clip_{i}")
            start = round(float(clip["start"]), 2)
            end = round(float(clip["end"]), 2)
            duration = round(end - start, 2)

            if duration <= 0: continue

            safe_title = "".join(c if c.isalnum() or c in " _-" else "" for c in title).strip()[:50]
            output_path = os.path.join(output_folder, f"{i:02d}_{safe_title}.mp4")

            # Print de cabeçalho limpo
            print(f"\n🎬 CLIP {i:02d}/{len(all_flattened_clips):02d} | {safe_title}")
            print(f"⏱️  Início: {format_time(start)} | Fim: {format_time(end)} | Total: {duration:2.2f}s")

            # Cria arquivo SRT temporário para este clip se houver transcrição
            srt_temp_path = None
            has_subtitles = False
            if transcript_segments:
                srt_temp_path = os.path.join(output_folder, f"temp_clip_{i}.srt")
                has_subtitles = create_srt_for_clip(transcript_segments, start, end, srt_temp_path)

            # Filtro visual base
            filter_complex = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:10[bg];"
                "[0:v]scale=1080:-1[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
            )
            
            # Adiciona legendas ao filtro se disponível
            if has_subtitles and srt_temp_path:
                # Converte para caminho absoluto e formata para FFmpeg (barra dupla)
                srt_abs_path = os.path.abspath(srt_temp_path)
                # No Windows, FFmpeg precisa de barras duplas escapadas
                srt_path_escaped = srt_abs_path.replace('\\', '\\\\\\\\').replace(':', '\\:')
                # Estilo otimizado para Reels/Shorts: fonte menor, bem próximo do fundo
                # MarginV=50 = muito próximo do fundo / FontSize=18 = letra menor ainda
                
                filter_complex += (
                  f";[v]subtitles='{srt_path_escaped}':force_style="
                  f"'FontName=Ubuntu,"        # Fonte simples e legível
                  f"FontSize=12,"            # Tamanho ajustado para 1080p
                  f"Bold=1,"                 # Texto em negrito para destacar
                  f"PrimaryColour=&H00FFFFFF," # Texto Branco
                  f"BorderStyle=1,"          # MODO CAIXA (Opaque Box)
                  f"BackColour=&H80000000,"  # Cor do fundo (Preto com 50% de transparência)
                  f"Outline=2,"              # Remove a borda do texto
                  f"OutlineColour=&H80000000," # Cor da borda (Preto translúcido)
                  f"Shadow=0,"               # Remove a sombra para ficar flat
                  f"MarginV=25,"             # Sobe a legenda para não ficar colada na borda inferior
                  f"Alignment=2'[vout]"      # Centralizado embaixo
              )
                video_map = "[vout]"
            else:
                video_map = "[v]"

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-t", str(duration),
                "-filter_complex", filter_complex,
                "-map", video_map,
                "-map", "0:a",
                # "-c:v", "libx264", # Troque para libx264 se quiser usar a CPU
                "-c:v", "h264_nvenc", # Troque para h264_nvenc se quiser usar a GPU
                "-preset", "p4",  # p4 = balanced preset for nvenc (p1=fastest, p7=slowest)
                "-cq", "23",  # Use -cq (constant quality) instead of -crf for nvenc
                "-c:a", "aac",
                "-b:a", "128k",
                "-progress", "pipe:1",
                "-nostats",
                output_path
            ]

            run_ffmpeg_with_progress(cmd, duration)
            
            # Remove arquivo SRT temporário
            if srt_temp_path and os.path.exists(srt_temp_path):
                os.remove(srt_temp_path)
            
            print(f"✅ CONCLUÍDO: {os.path.basename(output_path)}")
            success_count += 1

        except Exception as e:
            print(f"❌ ERRO NO CLIP {i}: {e}")
            error_count += 1
            # Remove arquivo SRT temporário em caso de erro
            if srt_temp_path and os.path.exists(srt_temp_path):
                try:
                    os.remove(srt_temp_path)
                except:
                    pass
            continue
    
    # Sumário final
    print(f"\n{'='*50}")
    print(f"✅ Clips processados com sucesso: {success_count}/{len(all_flattened_clips)}")
    if error_count > 0:
        print(f"❌ Clips com erro: {error_count}")
    print(f"{'='*50}")