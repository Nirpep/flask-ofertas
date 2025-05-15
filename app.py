from flask import Flask, request, render_template, redirect
import pandas as pd
import pyodbc
import os
from datetime import datetime

app = Flask(__name__)

# === Configuración de SQL Server ===
server = os.getenv("DB_SERVER")
database = os.getenv("DB_NAME")
username = os.getenv("DB_USER")
password = os.getenv("DB_PASS")
tabla = 'ofertas'


conn_str = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={server};DATABASE={database};UID={username};PWD={password}"
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_excel():
    archivo = request.files['archivo_excel']

    if archivo.filename == '':
        return "No se seleccionó archivo."

    try:
        df = pd.read_excel(archivo)
        df.columns = ['id_articulo', 'Preciooferta', 'fechaTermino']
        df['id_articulo'] = df['id_articulo'].astype(int)
        df['Preciooferta'] = df['Preciooferta'].astype(float)
        df['fechaTermino'] = pd.to_datetime(df['fechaTermino'], errors='coerce')
        df = df.dropna(subset=['fechaTermino'])
    except Exception as e:
        return f"Error al procesar el Excel: {e}"

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Crear tabla temporal
        cursor.execute("""
        IF OBJECT_ID('tempdb..#TempOferta') IS NOT NULL DROP TABLE #TempOferta;

        CREATE TABLE #TempOferta (
            id_articulo INT,
            Preciooferta DECIMAL(10,2),
            fechaTermino DATE
        )
        """)
        conn.commit()

        # Insertar en tabla temporal
        for _, row in df.iterrows():
            cursor.execute(
                "INSERT INTO #TempOferta (id_articulo, Preciooferta, fechaTermino) VALUES (?, ?, ?)",
                row['id_articulo'], row['Preciooferta'], row['fechaTermino'].date()
            )
        conn.commit()

        # MERGE con destino
        cursor.execute(f"""
        MERGE INTO {tabla} AS destino
        USING #TempOferta AS origen
        ON destino.id_articulo = origen.id_articulo AND destino.fechaTermino = origen.fechaTermino

        WHEN MATCHED THEN
            UPDATE SET Preciooferta = origen.Preciooferta

        WHEN NOT MATCHED THEN
            INSERT (id_articulo, Preciooferta, fechaTermino)
            VALUES (origen.id_articulo, origen.Preciooferta, origen.fechaTermino);
        """)
        conn.commit()

        cursor.close()
        conn.close()

        return "Excel procesado correctamente: datos insertados o actualizados."

    except Exception as e:
        return f"Error al conectar o procesar en SQL Server: {e}"

if __name__ == '__main__':
    app.run(debug=True)
