import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import joblib
import os

def entrenar_sistema():
    # Rutas
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta_original = os.path.join(base_dir, 'data', 'raw', 'email-spam-classification-dataset-csv', 'emails.csv')
    # Intentamos buscar el archivo de refuerzo
    ruta_refuerzo = os.path.join(base_dir, 'refuerzo_espanol.csv')
    if not os.path.exists(ruta_refuerzo):
        ruta_refuerzo = os.path.join(base_dir, 'data', 'refuerzo_espanol.csv')
    
    print("🔄 Iniciando re-entrenamiento automático...")

    # 1. Cargar Dataset Original 
    try:
        df_original = pd.read_csv(ruta_original, encoding='utf-8')
        df_original = df_original[['message', 'spam']]
    except:
        df_original = pd.DataFrame(columns=['message', 'spam'])

    # 2. Cargar Dataset de Refuerzo 
    try:
        if os.path.exists(ruta_refuerzo) and os.path.getsize(ruta_refuerzo) > 0:
            # header=None ayuda si el archivo no tiene títulos
            df_refuerzo = pd.read_csv(ruta_refuerzo, encoding='utf-8', header=None, names=['message', 'spam'])
            
            # Limpieza: Si la primera fila es el título 
            if len(df_refuerzo) > 0 and str(df_refuerzo.iloc[0]['message']).strip() == 'message':
                df_refuerzo = df_refuerzo.iloc[1:]
        else:
            df_refuerzo = pd.DataFrame(columns=['message', 'spam'])
    except Exception as e:
        print(f"⚠️ Error leyendo refuerzo: {e}")
        df_refuerzo = pd.DataFrame(columns=['message', 'spam'])

    # 3. Unir
    df_total = pd.concat([df_original, df_refuerzo], ignore_index=True)
    
    # LIMPIEZA DE DATOS
    df_total['spam'] = pd.to_numeric(df_total['spam'], errors='coerce')
    
    df_total.dropna(subset=['spam', 'message'], inplace=True)
    
    # 3. Aseguramos que el mensaje sea texto
    df_total['message'] = df_total['message'].astype(str)
    
    print(f"📚 Entrenando con {len(df_total)} ejemplos válidos.")

    if len(df_total) == 0:
        print("❌ Error crítico: No hay datos válidos para entrenar.")
        return

    # 4. Entrenar
    vectorizer = CountVectorizer()
    X = vectorizer.fit_transform(df_total['message'])
    y = df_total['spam']

    model = MultinomialNB()
    model.fit(X, y)

    # 5. Guardar
    models_dir = os.path.join(base_dir, 'models')
    os.makedirs(models_dir, exist_ok=True)

    joblib.dump(model, os.path.join(models_dir, 'modelo_spam_entrenado.pkl'))
    joblib.dump(vectorizer, os.path.join(models_dir, 'vectorizador.pkl'))

    print("✅ Sistema re-entrenado y guardado correctamente.")

if __name__ == "__main__":
    entrenar_sistema()