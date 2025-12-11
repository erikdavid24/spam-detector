import pandas as pd
import os
import urllib.request
import zipfile
import io


base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ruta_carpeta = os.path.join(base_dir, 'data', 'raw', 'email-spam-classification-dataset-csv')
ruta_archivo_malo = os.path.join(ruta_carpeta, 'emails.csv')

if os.path.exists(ruta_archivo_malo):
    print(f"🗑️ Borrando archivo incorrecto: {ruta_archivo_malo}")
    os.remove(ruta_archivo_malo)
else:
    print("info: El archivo viejo no existía, continuamos.")

os.makedirs(ruta_carpeta, exist_ok=True)

url = "https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip"
print("⬇️ Descargando dataset correcto (Texto real en Inglés)...")

try:
    response = urllib.request.urlopen(url)
    with zipfile.ZipFile(io.BytesIO(response.read())) as z:
        with z.open('SMSSpamCollection') as f:  
            df = pd.read_csv(f, sep='\t', header=None, names=['label', 'message'])
    df['spam'] = df['label'].map({'ham': 0, 'spam': 1})
    df = df[['message', 'spam']]
    df.to_csv(ruta_archivo_malo, index=False, encoding='utf-8')
    
    print(f"✅ ¡Éxito! Nuevo archivo creado en: {ruta_archivo_malo}")
    print(f"   Muestra del contenido:\n{df.head(3)}")

except Exception as e:
    print(f"❌ Error al descargar: {e}")