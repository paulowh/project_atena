import cv2
import base64
import requests

def analyze_frame_with_llava(video_path, timestamp, prompt):
    # 1. Extrai o frame usando OpenCV
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
    success, frame = cap.read()
    if not success: return None
    
    # 2. Converte para Base64 (formato que o Ollama aceita para imagens)
    _, buffer = cv2.imencode('.jpg', frame)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    # 3. Chama o Ollama com o modelo LLaVA
    payload = {
        "model": "llava",
        "prompt": prompt,
        "stream": False,
        "images": [img_base64]
    }
    
    response = requests.post("http://localhost:11434/api/generate", json=payload)
    return response.json().get("response")