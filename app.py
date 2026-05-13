import os
import subprocess
import glob
import urllib.parse
from flask import Flask, request, jsonify, send_from_directory, Response

app = Flask(__name__)
DOWNLOAD_DIR = "downloads"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def limpiar_carpeta_temporal():
    """Limpieza de seguridad por si algún proceso se interrumpió abruptamente antes."""
    archivos = glob.glob(os.path.join(DOWNLOAD_DIR, '*'))
    for f in archivos:
        try:
            os.remove(f)
        except Exception:
            pass

@app.route('/')
def index():
    return send_from_directory('.', 'index.html', mimetype='text/html')

@app.route('/api/download', methods=['POST'])
def download_clip():
    limpiar_carpeta_temporal()
    
    data = request.json
    video_id = data.get('video_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    format_type = data.get('format_type', 'mp4')
    quality = data.get('quality', 'best')

    if not all([video_id, start_time is not None, end_time is not None]):
        return jsonify({"error": "Faltan datos en la solicitud"}), 400

    url = f"https://www.youtube.com/watch?v={video_id}"
    
    command = [
        "yt-dlp",
        "--download-sections", f"*{start_time}-{end_time}",
        "--force-keyframes-at-cuts",
        "--ffmpeg-location", "/usr/bin/ffmpeg",
    ]

    output_template = os.path.join(DOWNLOAD_DIR, f"%(title)s_[{int(start_time)}s-{int(end_time)}s].%(ext)s")

    if format_type == 'mp3':
        command.extend(["-f", "bestaudio/best", "-x", "--audio-format", "mp3", "-o", output_template])
    else:
        format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4" if quality == 'best' else f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/mp4"
        command.extend(["-f", format_string, "-o", output_template])

    command.append(url)

    try:
        # Ejecutamos yt-dlp
        subprocess.run(command, check=True, capture_output=True)
        
        archivos_generados = os.listdir(DOWNLOAD_DIR)
        if not archivos_generados:
            return jsonify({"error": "No se generó el archivo de salida"}), 500
            
        archivo_final = archivos_generados[0]
        ruta_final = os.path.join(DOWNLOAD_DIR, archivo_final)
        
        # LÓGICA DE STREAMING Y DESTRUCCIÓN
        def stream_and_remove():
            with open(ruta_final, 'rb') as f:
                # Leemos y enviamos en bloques de 4KB
                while chunk := f.read(4096):
                    yield chunk
            # Esta línea se ejecuta automáticamente cuando el archivo se termina de leer por completo
            try:
                os.remove(ruta_final)
            except Exception as e:
                print(f"Error al borrar el archivo residual: {e}")

        # Extraemos el peso del archivo para que el navegador muestre la barra de progreso correctamente
        file_size = os.path.getsize(ruta_final)
        nombre_seguro = urllib.parse.quote(archivo_final)
        
        respuesta = Response(stream_and_remove(), direct_passthrough=True)
        respuesta.headers["Content-Length"] = str(file_size)
        respuesta.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{nombre_seguro}"
        respuesta.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        
        if format_type == 'mp3':
            respuesta.mimetype = 'audio/mpeg'
        else:
            respuesta.mimetype = 'video/mp4'
            
        return respuesta
        
    except subprocess.CalledProcessError as e:
        print(f"Error técnico: {e.stderr.decode()}")
        return jsonify({"error": "Error al procesar el video"}), 500

if __name__ == '__main__':
    print("Servidor iniciado. Abrí: http://localhost:5000")
    app.run(debug=True, port=5000)