from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
import json
import io
import csv
import pandas as pd
from datetime import datetime
import requests  # <- para llamar a la API externa

app = Flask(__name__)

DB_NAME = 'inventario.db'
BARCODE_LOOKUP_API_KEY = '7f83nsq37a057x26eyb2hns85243zg'  # Pon aquí tu API Key real

# Crear tabla inventario si no existe
def crear_tabla():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            cantidad INTEGER,
            codigo_unico TEXT,
            codigo_barras TEXT,
            title TEXT,
            tamano TEXT,
            marca TEXT
        )
    ''')
    conn.commit()
    conn.close()

crear_tabla()

# Función para buscar producto en Barcode Lookup API
def buscar_producto_barcode_lookup(codigo_barras):
    url = f'https://api.barcodelookup.com/v3/products?barcode={codigo_barras}&key={BARCODE_LOOKUP_API_KEY}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if 'products' in data and len(data['products']) > 0:
            producto = data['products'][0]
            descripcion = producto.get('title', 'Sin descripción')
            tamano = producto.get('size', 'Sin tamaño')
            marca = producto.get('brand', 'Sin marca')
            codigo_unico = producto.get('barcode_number', codigo_barras)

            return {
                'codigo_unico': codigo_unico,
                'codigo_barras': codigo_barras,
                'descripcion': descripcion,
                'tamano': tamano,
                'marca': marca
            }
        else:
            return None
    except requests.RequestException as e:
        print(f"Error llamando a Barcode Lookup API: {e}")
        return None


@app.route('/')
def index():
    # Mostrar tabla inventario
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventario ORDER BY fecha_hora DESC')
    rows = cursor.fetchall()
    conn.close()
    return render_template('index.html', inventario=rows)


@app.route('/guardar', methods=['POST'])
def guardar():
    data = request.json
    codigo_barras = data.get('codigo_barras')
    cantidad = int(data.get('cantidad', 1))
    if not codigo_barras:
        return jsonify({'error': 'No se recibió código de barras'}), 400

    producto = buscar_producto_barcode_lookup(codigo_barras)
    if not producto:
        return jsonify({'error': 'Producto no encontrado'}), 404

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT INTO inventario (fecha_hora, cantidad, codigo_unico, codigo_barras, descripcion, tamano, marca)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        fecha_hora,
        cantidad,
        producto['codigo_unico'],
        producto['codigo_barras'],
        producto['descripcion'],
        producto['tamano'],
        producto['marca']
    ))
    conn.commit()
    conn.close()
    return jsonify({'mensaje': 'Producto guardado correctamente'}), 200

@app.route('/exportar_y_borrar/<formato>', methods=['POST'])
def exportar_y_borrar(formato):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query('SELECT * FROM inventario ORDER BY fecha_hora DESC', conn)

    if formato == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        archivo = io.BytesIO(output.getvalue().encode())
        mimetype = 'text/csv'
        filename = 'inventario.csv'
    elif formato == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
        output.seek(0)
        archivo = output
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        filename = 'inventario.xlsx'
    else:
        return "Formato no soportado", 400

    cursor = conn.cursor()
    cursor.execute('DELETE FROM inventario')
    conn.commit()
    conn.close()

    return send_file(
        archivo,
        mimetype=mimetype,
        as_attachment=True,
        download_name=filename
    )

@app.route('/exportar/<formato>')
def exportar(formato):
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query('SELECT * FROM inventario ORDER BY fecha_hora DESC', conn)
    conn.close()

    if formato == 'csv':
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            mimetype='text/csv',
            as_attachment=True,
            download_name='inventario.csv'
        )
    elif formato == 'excel':
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Inventario')
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='inventario.xlsx'
        )
    else:
        return "Formato no soportado", 400


if __name__ == '__main__':
    app.run(debug=True)
