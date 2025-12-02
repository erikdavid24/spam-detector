import flask
from flask import Flask, request, render_template
import pandas as pd
import joblib
import os
from deep_translator import GoogleTranslator

app = Flask(__name__)

# --- CARGA DE RECURSOS (MODELO Y VOCABULARIO) ---
print("🔄 Cargando modelo y vocabulario...")

# 1. Cargar tu modelo entrenado
ruta_modelo = '../models/modelo_spam_entrenado.pkl'
# Ajuste de ruta: si ejecutas desde la carpeta raíz del proyecto, usa 'models/...'
if not os.path.exists(ruta_modelo):
    ruta_modelo = 'models/modelo_spam_entrenado.pkl'

if os.path.exists(ruta_modelo):
    model = joblib.load(ruta_modelo)
    print("✅ Modelo cargado.")
else:
    print("❌ ERROR: No encuentro el archivo .pkl")

# 2. Cargar el vocabulario desde tu CSV (emails.csv)
# Ajuste de ruta para que funcione tanto en notebooks como en la raíz
rutas_posibles = [
    r"c:\Users\eriko\Spam_Classifier_Project\data\raw\email-spam-classification-dataset-csv\emails.csv",
    "data/raw/email-spam-classification-dataset-csv/emails.csv"
]
ruta_datos = None
for r in rutas_posibles:
    if os.path.exists(r):
        ruta_datos = r
        break

columnas_palabras = []
if ruta_datos:
    # Leemos solo 1 fila para sacar los nombres de columnas rápido
    df_ref = pd.read_csv(ruta_datos, nrows=1)
    columnas_palabras = df_ref.drop(columns=['Email No.', 'Prediction']).columns
    print(f"✅ Vocabulario cargado ({len(columnas_palabras)} palabras).")
else:
    print("❌ ERROR CRÍTICO: No encuentro 'emails.csv' para leer el vocabulario.")

# --- LÓGICA DE CLASIFICACIÓN (Tu cerebro de IA) ---
def classify(text):
    try:
        # 1. Traducir (Español -> Inglés)
        traductor = GoogleTranslator(source='auto', target='en')
        mensaje_ingles = traductor.translate(text)
        print(f"Texto traducido: {mensaje_ingles}")

        # 2. Convertir texto a números (Bag of Words)
        datos_entrada = pd.DataFrame(0, index=[0], columns=columnas_palabras)
        palabras = mensaje_ingles.lower().split()
        
        for palabra in palabras:
            if palabra in datos_entrada.columns:
                datos_entrada.loc[0, palabra] += 1
        
        # 3. Predecir
        prediccion = model.predict(datos_entrada)[0]
        
        if prediccion == 1:
            return "¡CUIDADO! Es SPAM 🛑"
        else:
            return "Es Correo Seguro ✅"
            
    except Exception as e:
        print(f"Error: {e}")
        return "Error en el servidor"

# --- RUTAS DE FLASK (Igual que Azrael05) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/predict")
def inference():
    # Azrael usa GET y 'text' como parámetro
    text = str(request.args.get('text'))
    result = classify(text)
    return result

if __name__ == "__main__":
    app.run(debug=True)