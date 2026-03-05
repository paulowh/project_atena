import librosa
import numpy as np
import os

def get_emotional_segments(video_path, threshold_multiplier=2.0):
    """
    Analisa o áudio e retorna os tempos (segundos) onde o volume superou a média.
    """
    print(f"🔍 Analisando picos de emoção no áudio...")
    y, sr = librosa.load(video_path, sr=16000)
    
    # Calcula a energia (volume)
    energy = librosa.feature.rms(y=y)[0]
    times = librosa.frames_to_time(range(len(energy)), sr=sr)
    
    mean_energy = np.mean(energy)
    threshold = mean_energy * threshold_multiplier
    
    # Agrupa momentos acima do threshold
    highlights = []
    for i, e in enumerate(energy):
        if e > threshold:
            highlights.append(times[i])
            
    # Filtra para não pegar centenas de pontos próximos
    unique_highlights = []
    if highlights:
        unique_highlights.append(highlights[0])
        for h in highlights:
            if h - unique_highlights[-1] > 30: # Intervalo de 30s entre destaques
                unique_highlights.append(h)
                
    return unique_highlights