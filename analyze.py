"""
Este módulo proporciona un servidor Flask para analizar imágenes mediante modelos de aprendizaje automático.


"""
#======================================================================================================================================
# IMPORTS SERVIDOR FLASK
#======================================================================================================================================

from flask import Flask, request, jsonify
import requests
from flask_cors import CORS

#======================================================================================================================================
# Imports para el modelo
#======================================================================================================================================

from efficientnet.tfkeras import EfficientNetB0

import tensorflow as tf
from tensorflow.keras.preprocessing.image import img_to_array, load_img # type: ignore
import numpy as np
import pandas as pd
from PIL import Image
from tensorflow.keras.preprocessing.image import ImageDataGenerator # type: ignore

#======================================================================================================================================
# IMPORTS
#======================================================================================================================================

from io import BytesIO
import base64
import os
from urllib.parse import urlparse

#======================================================================================================================================
# VARIABLES GLOBALES
# =====================================================================================================================================  

rootPath = 'c:\\Users\\artur\\Desktop\\HTTP'             #DIRECTORIO RAIZ DE /TEMP
modelpath = '/Users/artur/Desktop/HTTP/modelos/EfficentNet0_95.h5'
modelClasifPath = '/Users/artur/Desktop/HTTP/modelos/best_model.h5'

#======================================================================================================================================
# VARIABLES ANALISIS
# =====================================================================================================================================  

target_size = (224, 224)
batch_size = 1
datagen_test = ImageDataGenerator(rescale=1. / 255)

app = Flask(__name__)
CORS(app)  # Habilitar CORS para todas las rutas del servidor

#CARGAR EL MODELO
model = tf.keras.models.load_model(modelpath, compile=False)
modelClas = tf.keras.models.load_model(modelClasifPath, compile=False)

@app.route("/")
def hello():
    """
    Ruta de prueba para verificar que el servidor está en funcionamiento.

    Returns:
        str: Mensaje de bienvenida.
    """
    return ("Analizador de imagenes")


@app.route("/analizar_url", methods=['POST'])
def analizar_url():

    """
    Analiza una imagen proporcionada a través de una URL.

    Request:
        json: JSON que contiene la URL de la imagen a analizar.

    Returns:
        Response: JSON con los resultados del análisis o un mensaje de error.
    """
    data = request.json
    image_url = data.get('url')
    print(f"URL recibida: {image_url}")

    response = requests.get(image_url)
    content_type = response.headers.get('content-type')

    print(content_type)

    if response.status_code == 200:

        if content_type and 'image' not in content_type:
                
            return jsonify({"error": "Response.Status: La URL no es de una imagen."}), 301
        
       
        try:
            # Descarga de la imagen.
            path = to_pathWEB(response.content, image_url)
    
           # Preparar la imagen.
            file_df = to_dataframe(path)
    
            # Analizar la imagen.
            results = analyze_df(file_df)

            return jsonify(results)
        except Exception as e:
            
            print(f"Se produjo un error: {str(e)}")

            return jsonify({"error": "Ocurrió un error durante el procesamiento de la imagen."}), 302
        
    
    else:
        return jsonify({"error": "Response.Status: La URL no existe."}), 300


@app.route('/analizar_imagen', methods=['POST'])
def analizar_imagen():
    """
    Analiza una imagen proporcionada a través de un archivo codificado en base64.

    Request:
        json: JSON que contiene el nombre del archivo de imagen guardado en el servidor para analizarla, asi como su ruta.

    Returns:
        Response: JSON con los resultados del análisis o un mensaje de error.
    """
    try:
        data = request.json

        image_file = data.get('file')
        username = data.get('user')

        #print(image_file)
        print(username)

        if image_file:
        
            path = to_path64(image_file,username)

            file_df = to_dataframe(path)

            results = analyze_df(file_df)

            return jsonify(results),200
        else:
            return jsonify({'prediction': 'fatal error'}),500
        

    except Exception as e:
        print("Error al analizar:", e)
        return jsonify({"error": "Ocurrió un error al analizar la imagen"}), 500



#======================================================================================================================================
# FUNCIONES
# =====================================================================================================================================  


#Guardar imagen de internet en directorio temporal para analisis
def to_pathWEB(image, image_url):
    """
    Guarda la imagen obtenida con la URL y descargada de internet en el servidor para su análisis.

    Args:
        image (bytes): El contenido de la imagen descargada.
        image_url (str): La URL de la imagen.

    Returns:
        str: La ruta del archivo de imagen guardado en el servidor.

    Example:
        >>> image_url = "http://example.com/image.jpg"
        >>> response = requests.get(image_url)
        >>> if response.status_code == 200:
        >>>     path = to_pathWEB(response.content, image_url)
        >>>     print(path)
    """
    filename = urlparse(image_url).path.split("/")[-1]
    path = rootPath + 'temp/user/' + filename
    print(path)

    with open(path, "wb") as f:
        f.write(image)

    print("PATH", path)

    return path

#Guardar imagen enviada como base64 en directorio temporal para analisis
def to_path64(image64,username):
    """
    Guarda una imagen enviada como base64 en el servidor para su análisis.

    Args:
        image64 (str): La imagen en formato base64.
        username (str): El nombre de la carpeta del usuario que solicita el analisis.

    Returns:
        str: La ruta del archivo de imagen guardado en el servidor.

    Raises:
        ValueError: Si ocurre un error al decodificar la imagen base64.
        IOError: Si ocurre un error al guardar la imagen en el disco.

    Example:
        >>> image64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."
        >>> username = "usuario_3"
        >>> path = to_path64(image64, username)
        >>> print(path)
    """
    try:
        content = image64.split(',')[1]
        path = os.path.join(rootPath, "users", username, "temp", "imagen_decodificada.png")

        image_data = base64.b64decode(content)
        image = Image.open(BytesIO(image_data))
        image.save(path, format="png")

        return path
    
    except (ValueError, IOError) as e:
        print(f"Error al guardar la imagen: {e}")
        raise


#Transforma un PATH en un Dataframe de DIM=1
def to_dataframe(path):
    """
    Transforma una ruta de imagen en un DataFrame de Pandas con dimensiones 1x4.

    Args:
        path (str): La ruta del archivo de imagen.

    Returns:
        pandas.DataFrame: Un DataFrame con las columnas 'Image', 'target', 'class', y 'path_jpeg'.

    Example:
        >>> path = "/path/a/la/imagen.jpg"
        >>> df = to_dataframe(path)
        >>> print(df)
            Image      target   class    path_jpeg
        0   imagen_33  unknown  unknown  /path/a/la/imagen_33.jpg
    """
    user='user'
    unknown='unknown'
    image_file=path

    df = pd.DataFrame({
    'Image': user,
    'target': unknown,
    'class': unknown,
    'path_jpeg': image_file
    }, index=range(0, 1))

    return df


#Analiza un DataFrame(DIM=1) y devuelve Probabilidad 
def analyze_df(df):
    """
    Analiza un DataFrame que contiene la ruta a una imágen y devuelve las predicciones del modelo.

    Esta función utiliza dos modelos preentrenados para hacer predicciones sobre las imágenes 
    proporcionadas en el DataFrame. Las predicciones incluyen tanto la probabilidad de malignidad de
    la lesión como la clasificación de la misma.

    Args:
        df (pandas.DataFrame): DataFrame con las rutas a las imágenes y otros metadatos.
            - 'path_jpeg': Columna con las rutas a las imágenes.
            - 'class': Columna con las etiquetas objetivo (aunque no se utiliza en la predicción tensorflow necesita la columna).
            - 'target': Columna con la clase objetivo (maligno/benigno) (aunque no se utiliza en la predicción tensorflow necesita la columna).

    Returns:
        - 'predictions': Lista de predicciones redondeadas.
    
    Example:
        >>> df = pd.DataFrame({
        >>>     'path_jpeg': ['/path/to/image1.jpg'],
        >>>     'class': ['unknown']
        >>>     'target': ['unknown']
        >>> })
        >>> results = analyze_df(df)
        >>> print(results)
        {'predictions': [23.45, 12.34, 56.78, ...]}
    """
    test_generator = datagen_test.flow_from_dataframe(
        df,
        x_col = 'path_jpeg',
        y_col = 'target',
        target_size=target_size,
        batch_size=batch_size,
        shuffle=False
    )
    print(df)
    test_generator_clas = datagen_test.flow_from_dataframe(
        df,
        x_col = 'path_jpeg',
        #y_col = ['MEL', 'NV', 'BCC', 'AKIEC', 'BKL', 'DF', 'VASC'],
        target_size=target_size,
        batch_size=batch_size,
        class_mode='categorical',
        shuffle=False
    )

    prediction = model.predict(test_generator)
    predictions = modelClas.predict(test_generator_clas)

    array = np.concatenate((prediction, predictions), axis=1)
    #prediction_value = [prediction_value] + [lista]
    print(array,prediction,predictions)
    
    lista = []
    for prediccion in array[0]:
        lista.append(round(prediccion * 100, 2))

    print(test_generator_clas.labels)
    print(lista)
    #SUPONEMOS {'AKIEC': 0, 'BCC': 1, 'BKL': 2, 'DF': 3, 'MEL': 4, 'NV': 5, 'VASC': 6}
    #TO        {'MEL': 4, 'NV': 5, 'BCC': 1, 'AKIEC': 0, 'BKL': 2, 'DF': 3, 'VASC': 6}
    lista[1], lista[2], lista[3], lista[4], lista[5], lista[6], lista[7] = lista[5], lista[6], lista[2], lista[1], lista[3], lista[4], lista[7]

    print(lista)
   

    results = {'predictions': lista}
    return results


# Función para preparar la imagen URL (NO USADO)
def preprocess_image(image):
    image = tf.keras.preprocessing.image.array_to_img(image)
    image = image.resize((224, 224))  # Redimensionar la imagen al tamaño esperado
    image = img_to_array(image)
    image = np.expand_dims(image, axis=0)
    return image


#Analiza una Imagen (NO OPTIMO) (NO USADO)
def analyze_image(image):

    image_generator = datagen_test.flow(image)

    predictions = model.predict(image_generator)
    print(predictions)
    prediction_value = round((predictions[0][0])*100, 2)

    results = {'prediction': prediction_value}
    return results


#Guardar imagen en directorio temporal para analisis (NO USADO)
def to_path(file):
    
    fileName = file.filename
    path = rootPath + 'users/ARTURO/temp/' + fileName
    print(path)

    file.save(path)
    print("PATH", path)

    return path


#if __name__ == "__main__":
    #os.system("gunicorn -b 0.0.0.0:5000 analyze:app")
    #app.run(host="0.0.0.0",port=5000)
    #from waitress import serve # type: ignore
    #serve(analyze.app, host='0.0.0.0', port=5000)