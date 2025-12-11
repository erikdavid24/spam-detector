from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_socketio import SocketIO, emit
from src.leer_correos import obtener_correos
from src.reentrenar import entrenar_sistema
import os
import json
import time
import re # <--- Para buscar el @dominio.com
from threading import Thread
from collections import Counter

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_proy_escolar'

socketio = SocketIO(app, cors_allowed_origins="*")

# --- MEMORIA CACHÉ ---
cache_correos = {
    'inbox': [],
    'spam': []
}

def calcular_estadisticas():
    inbox = cache_correos['inbox']
    spam = cache_correos['spam']
    
    total = len(inbox) + len(spam)
    if total == 0: return None

    # 1. Datos para gráfica de Dona (Porcentajes)
    porc_spam = round((len(spam) / total) * 100, 1)
    porc_inbox = round((len(inbox) / total) * 100, 1)

    # 2. Datos para gráfica de Barras (Palabras top en Spam)
    # Juntamos todos los asuntos de spam en un solo texto gigante
    texto_spam = " ".join([email['asunto'] for email in spam]).lower()
    # Quitamos palabras aburridas (stopwords básicas)
    palabras_ignoradas = ['de', 'la', 'el', 'en', 'y', 'a', 'que', 'los', 'del', 'se', 'por', 'un', 'una', 'su', 'para', 'con', 'no', 'si']
    palabras = [p for p in texto_spam.split() if len(p) > 3 and p not in palabras_ignoradas]
    
    # Contamos las 5 más comunes
    top_palabras = Counter(palabras).most_common(5)
    
    return {
        'resumen': [len(inbox), len(spam)],
        'top_palabras': [x[0] for x in top_palabras],
        'conteo_palabras': [x[1] for x in top_palabras]
    }

@app.route('/api/stats')
def api_stats():
    stats = calcular_estadisticas()
    return jsonify(stats)

hilo_gmail = None

def vigilar_gmail():
    global cache_correos
    print("🕵️‍♂️ Vigilante de Gmail iniciado...")
    while True:
        try:
            todos = obtener_correos()
            nuevos_inbox = [e for e in todos if not e['es_spam']]
            nuevos_spam = [e for e in todos if e['es_spam']]
            
            cache_correos['inbox'] = nuevos_inbox
            cache_correos['spam'] = nuevos_spam
            
            socketio.emit('actualizacion_inbox', nuevos_inbox)
            socketio.emit('actualizacion_spam', nuevos_spam)
            socketio.sleep(10)
        except Exception as e:
            print(f"⚠️ Error en vigilante: {e}")
            socketio.sleep(10)

#Helper para extraer dominio (ej: "amazon.com" de "ventas@amazon.com")
def extraer_dominio(remitente):
    try:
        # Busca lo que hay después del @ y antes del cierre > o espacio
        # Ej: "Erik <erik@google.com>" -> "google.com"
        match = re.search(r"@([\w\.-]+)", remitente)
        if match:
            return match.group(1).lower()
    except:
        pass
    return None

# --- RUTAS WEB ---
@app.route('/')
def inicio():
    return redirect(url_for('inbox'))

@app.route('/inbox')
def inbox():
    return render_template('gmail_style.html', pagina_actual='inbox', emails=cache_correos['inbox'])

@app.route('/spam')
def spam():
    return render_template('gmail_style.html', pagina_actual='spam', emails=cache_correos['spam'])

@app.route('/api/obtener_emails')
def api_emails():
    tipo = request.args.get('tipo', 'inbox')
    return jsonify(cache_correos[tipo])

# --- RUTAS DE CORRECCIÓN (AQUÍ ESTÁ LA MAGIA NUEVA) ---
@app.route('/corregir_lote', methods=['POST'])
def corregir_lote():
    asuntos = request.form.getlist('asuntos')
    etiqueta = request.form['etiqueta_correcta'] # '0' (No es Spam) o '1' (Es Spam)
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. ACTUALIZAR CORRECCIONES MANUALES (JSON)
    ruta_correcciones = os.path.join(base_dir, 'data', 'correcciones.json')
    try:
        with open(ruta_correcciones, 'r', encoding='utf-8') as f:
            correcciones = json.load(f)
    except: correcciones = {}
    
    for asunto in asuntos:
        correcciones[asunto] = int(etiqueta)
    
    with open(ruta_correcciones, 'w', encoding='utf-8') as f:
        json.dump(correcciones, f, indent=4)
    
    # 2. INTELIGENCIA DE DOMINIOS (WHITELIST AUTOMÁTICA)
    # Si el usuario dijo "NO ES SPAM" ('0'), confiamos en el dominio
    if etiqueta == '0':
        print("🛡️ Aprendiendo nuevos dominios confiables...")
        ruta_whitelist = os.path.join(base_dir, 'data', 'whitelist.json')
        
        try:
            with open(ruta_whitelist, 'r', encoding='utf-8') as f:
                whitelist = json.load(f)
        except: whitelist = []

        # Buscamos el remitente original en nuestra caché (porque el form solo mandó el asunto)
        # Buscamos en la carpeta de SPAM porque de ahí los estamos sacando
        correos_en_spam = cache_correos['spam']
        
        nuevos_dominios = []
        for asunto in asuntos:
            # Buscamos el correo que tenga ese asunto
            email_obj = next((e for e in correos_en_spam if e['asunto'] == asunto), None)
            
            if email_obj:
                dominio = extraer_dominio(email_obj['remitente'])
                if dominio and dominio not in whitelist:
                    whitelist.append(dominio)
                    nuevos_dominios.append(dominio)
        
        # Guardamos la nueva Whitelist
        if nuevos_dominios:
            with open(ruta_whitelist, 'w', encoding='utf-8') as f:
                json.dump(whitelist, f, indent=4)
            print(f"✅ Dominios agregados a lista segura: {nuevos_dominios}")

    # 3. RE-ENTRENAR MODELO
    entrenar_sistema()

    # 4. ACTUALIZAR RÁPIDO
    socketio.start_background_task(vigilar_gmail_una_vez)

    if etiqueta == '0': return redirect(url_for('inbox'))
    else: return redirect(url_for('spam'))

def vigilar_gmail_una_vez():
    socketio.sleep(1)
    # Forzamos una lectura inmediata para actualizar la UI
    with app.app_context():
        try:
            todos = obtener_correos()
            cache_correos['inbox'] = [e for e in todos if not e['es_spam']]
            cache_correos['spam'] = [e for e in todos if e['es_spam']]
            socketio.emit('actualizacion_inbox', cache_correos['inbox'])
            socketio.emit('actualizacion_spam', cache_correos['spam'])
        except: pass

@socketio.on('connect')
def test_connect():
    global hilo_gmail
    if hilo_gmail is None:
        hilo_gmail = socketio.start_background_task(vigilar_gmail)

if __name__ == '__main__':
    print("🚀 Servidor Arrancando...")
    try:
        todos = obtener_correos()
        cache_correos['inbox'] = [e for e in todos if not e['es_spam']]
        cache_correos['spam'] = [e for e in todos if e['es_spam']]
        print("✅ Caché lista.")
    except:
        print("⚠️ Caché vacía al inicio.")

    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)