import imaplib
import email
from email.header import decode_header
import joblib
import os
import json
import re 
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

# --- RUTAS ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'modelo_spam_entrenado.pkl')
VECTORIZER_PATH = os.path.join(BASE_DIR, 'models', 'vectorizador.pkl')
WHITELIST_PATH = os.path.join(BASE_DIR, 'data', 'whitelist.json')
CORRECCIONES_PATH = os.path.join(BASE_DIR, 'data', 'correcciones.json')

# --- CREDENCIALES ---
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASS = os.getenv('EMAIL_PASS')
IMAP_HOST = os.getenv('IMAP_HOST')

def cargar_ia():
    try:
        modelo = joblib.load(MODEL_PATH)
        vectorizador = joblib.load(VECTORIZER_PATH)
        return modelo, vectorizador
    except: return None, None

def cargar_json(ruta):
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {} if 'correcciones' in ruta else []

def limpiar_decodificacion(bytes_dato):
    if not bytes_dato: return ""
    codificaciones = ['utf-8', 'latin-1', 'iso-8859-1']
    for cod in codificaciones:
        try: return bytes_dato.decode(cod)
        except: continue
    return bytes_dato.decode('utf-8', errors='ignore')

# Función para barrer etiquetas HTML (<div>, <br>, <img>, etc.)
def quitar_html(texto):
    limpio = re.sub(r'<[^>]+>', ' ', texto)
    return " ".join(limpio.split())

def obtener_correos():
    modelo, vectorizador = cargar_ia()
    
    dominios_seguros = cargar_json(WHITELIST_PATH)
    decisiones_humanas = cargar_json(CORRECCIONES_PATH)
    
    correos_procesados = [] 
    if not modelo: return []

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # Buscamos todos los correos
        status, messages = mail.search(None, "ALL")
        if not messages[0]: return []

        # Leemos los últimos 10 (invertimos la lista)
        email_ids = messages[0].split()[::-1]
        limit = 10 
        contador = 0

        for email_id in email_ids:
            if contador >= limit: break
            
            try:
                res, msg = mail.fetch(email_id, "(RFC822)")
                for response in msg:
                    if isinstance(response, tuple):
                        msg = email.message_from_bytes(response[1])
                        
                        # --- DECODIFICAR ASUNTO ---
                        subject_bytes, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject_bytes, bytes):
                            try: subject = subject_bytes.decode(encoding or 'utf-8')
                            except: subject = limpiar_decodificacion(subject_bytes)
                        else: subject = subject_bytes

                        # --- DECODIFICAR CUERPO ---
                        body = "Sin contenido"
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type == "text/plain":
                                    body = limpiar_decodificacion(part.get_payload(decode=True))
                                    break
                                elif content_type == "text/html":
                                    # Si solo hay HTML, lo limpiamos
                                    html_raw = limpiar_decodificacion(part.get_payload(decode=True))
                                    body = quitar_html(html_raw)
                        else:
                            content = limpiar_decodificacion(msg.get_payload(decode=True))
                            if msg.get_content_type() == "text/html":
                                body = quitar_html(content)
                            else:
                                body = content

                        # 1. Cuerpo limpio para mostrar en el modal (sin HTML)
                        cuerpo_completo = quitar_html(body)
                        
                        # 2. Resumen corto para la lista (sin saltos de línea)
                        resumen_limpio = cuerpo_completo.replace('\n', ' ').replace('\r', '')

                        # 1. ¿El humano ya decidió? (Correcciones)
                        if subject in decisiones_humanas:
                            prediccion = decisiones_humanas[subject]
                        else:
                            # 2. ¿Es dominio seguro? (Whitelist)
                            remitente = msg.get('From', '').lower()
                            es_seguro = any(d in remitente for d in dominios_seguros)
                            
                            if es_seguro:
                                prediccion = 0 # Ham
                            else:
                                # 3. Preguntar a la IA 
                                contenido_analisis = f"{subject} {cuerpo_completo}"
                                vec = vectorizador.transform([contenido_analisis])
                                prediccion = modelo.predict(vec)[0]

                        correos_procesados.append({
                            'remitente': msg.get('From'),
                            'asunto': subject,
                            'resumen': resumen_limpio[:80] + "...", 
                            'cuerpo_completo': cuerpo_completo, 
                            'es_spam': int(prediccion) == 1 
                        })
                        contador += 1
            except Exception as e:
                continue

        mail.logout()
        return correos_procesados

    except Exception as e:
        print(f"❌ Error conexión: {e}")
        return []