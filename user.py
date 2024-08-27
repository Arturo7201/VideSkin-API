"""
Este módulo proporciona un servidor Flask para la gestión de usuarios y de todos sus datos.

"""
#======================================================================================================================================
# IMPORTS SERVIDOR FLASK
#======================================================================================================================================

from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
import requests
import json

#======================================================================================================================================
# IMPORTS
#======================================================================================================================================

import os
import shutil
import base64
import time
from PIL import Image
from io import BytesIO
import re
import numpy as np
from urllib.parse import urlparse

import sqlite3
import random

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import timedelta
from apscheduler.schedulers.background import BackgroundScheduler # type: ignore
from datetime import datetime


from apscheduler.schedulers.background import BackgroundScheduler

# =====================================================================================================================================  
#VARIABLES GLOBALES Y CORS
# =====================================================================================================================================  

database = "users.db"

months_translations = {
    "Jan": "ENE", "Feb": "FEB", "Mar": "MAR", "Apr": "ABR",
    "May": "MAY", "Jun": "JUN", "Jul": "JUL", "Aug": "AGO",
    "Sep": "SEP", "Oct": "OCT", "Nov": "NOV", "Dec": "DIC"
}

app = Flask(__name__)
CORS(app)

app.config['DIRECTORIO_RAIZ'] = 'c:\\Users\\artur\\Desktop\\HTTP'
scheduler = BackgroundScheduler()
scheduler.start()

# =====================================================================================================================================
# Configuración de Flask-JWT-Extended
# =====================================================================================================================================

app.config['JWT_SECRET_KEY'] = 'secreto'  # Clave secreta para firmar el token JWT CAMBIAR¿¿¿¿¿¿¿¿¿¿¿¿¿¿¿¿¿¿¿¿

# Configuración adicional
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)  # Tiempo de expiración del token (30 minutos)
#app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30)  # Tiempo de expiración del token de refresco (30 días)
app.config['JWT_BLACKLIST_ENABLED'] = True  # Habilitar lista negra de tokens
app.config['JWT_BLACKLIST_TOKEN_CHECKS'] = ['access', 'refresh']  # Revisar tanto los tokens de acceso como los de refresco

jwt = JWTManager(app)


# =====================================================================================================================================  
#CODIGO QUE SE EJECUTA AL ENCENDER EL SERVIDOR (CREAR BASE DE DATOS SI NO EXISTE)
# =====================================================================================================================================  

conn = sqlite3.connect(database)
cursor = conn.cursor()
create_table_users = """
CREATE TABLE IF NOT EXISTS Users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    surname TEXT NOT NULL,
    username TEXT NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    validation BOOLEAN DEFAULT FALSE,
    code TEXT,
    role INTEGER NOT NULL
);
"""
cursor.execute(create_table_users)

create_table_cribados = """
CREATE TABLE IF NOT EXISTS Cribados (
    id INTEGER PRIMARY KEY,
    id_user INTEGER NOT NULL,
    imagen TEXT,
    predicciones TEXT,
    FOREIGN KEY (id_user) REFERENCES Users(id) ON DELETE CASCADE
);
"""
cursor.execute(create_table_cribados)

create_table_recordatorios = """
CREATE TABLE IF NOT EXISTS Recordatorios (
    id INTEGER PRIMARY KEY,
    id_user INTEGER NOT NULL,
    id_job INTEGER NOT NULL,
    recordatorio TEXT,
    fecha INTEGER,
    FOREIGN KEY (id_user) REFERENCES Users(id)
);
"""
cursor.execute(create_table_recordatorios)


create_table_seguimiento = """
CREATE TABLE IF NOT EXISTS Seguimiento (
    id INTEGER PRIMARY KEY,
    id_user INTEGER NOT NULL,
    x INTEGER,
    y INTEGER,
    lugar TEXT,
    body TEXT,
    imagen TEXT,
    predicciones TEXT,
    FOREIGN KEY (id_user) REFERENCES Users(id)
);
"""
cursor.execute(create_table_seguimiento)


create_table_historial = """
CREATE TABLE IF NOT EXISTS Historial (
    id INTEGER PRIMARY KEY,
    id_lesion INTEGER NOT NULL,
    imagen TEXT,
    fecha INTEGER,
    predicciones TEXT,
    FOREIGN KEY (id_lesion) REFERENCES Seguimiento(id)
);
"""
cursor.execute(create_table_historial)


conn.commit()
conn.close()

# ===== GESTION USUARIOS     =====================================================================================================  

@app.route("/")
def hello():
    return ("Hello, World!")

# Punto final protegido
@app.route('/jwt', methods=['GET'])
@jwt_required()  # Proteger el punto final con autenticación JWT
def protected():
    """
    Punto final protegido que requiere autenticación JWT.

    Args:
        Token (JWT): Token de autentificación.

    :return: JSON con el usuario autenticado y su rol.
    :rtype: dict
    """
    current_user = get_jwt_identity()
    
    claims = get_jwt()
    user_role = claims.get('role', None)
    
    return jsonify(logged_in_as=current_user, role=user_role), 200


@app.route('/id', methods=['GET'])
@jwt_required()  # Proteger el punto final con autenticación JWT
def get_id():
    """
    Obtener el ID del usuario autenticado.

    Args:
        Token (JWT): Token de autentificación.

    :return: JSON con el ID del usuario.
    :rtype: dict
    """
    try:
        # Obtener el usuario actual autenticado desde el token JWT
        usuario_actual = get_jwt_identity()

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (usuario_actual,))
        id_user = cursor.fetchone()[0] 
        
        conn.close()


        return jsonify({"id": id_user})

    except Exception as e:
        print("Error al obtener el usuario:", e)
        return jsonify({"error": "Ocurrió un error al obtener el usuario"}), 500

@app.route('/getUsername', methods=['POST'])
@jwt_required() 
def get_username():
    """
    Obtener el username del usuario.

    Args:
        Token (JWT): Token de autentificación.

    :return: JSON con el ID del usuario.
    :rtype: dict
    """
    try:
        data = request.json
        id = data.get('id')

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT username FROM users WHERE id = ?", (id,))
        username = cursor.fetchone()[0] 
        
        conn.close()


        return jsonify({"username": username})

    except Exception as e:
        print("Error al obtener el usuario:", e)
        return jsonify({"error": "Ocurrió un error al obtener el usuario"}), 500


@app.route("/add", methods=["POST"])
def add_user():
    """
    Agregar un nuevo usuario a la base de datos.

    Args:
        json (dict): JSON con los datos del formulario que contiene:
            - name (str): Nombre del usuario.
            - surname (str): Apellido del usuario.
            - username (str): Nombre de usuario.
            - password (str): Contraseña del usuario.
            - email (str): Correo electrónico del usuario.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        # Obtener los datos del formulario desde el JSON de la solicitud
        data = request.json
        name = data['form']['name']
        surname = data['form']['surname']
        username = data['form']['username']
        password = data['form']['password']
        email = data['form']['email']
        code = generate_validation_code()

        # Validar los datos del formulario (Agregar validaciones segun requisitos)
        if not name or not surname or not username or not password or not email:
            return jsonify({"error": "Todos los campos son obligatorios"}), 400
        
        # Comprobar si el usuario ya existe en la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        existing_user = cursor.fetchone()
        conn.close()

        if existing_user:
            return jsonify({"error": "El nombre de usuario ya existe"}), 409  # Código 409 para Conflicto
        
        # Validar y sanitizar el nombre de la tabla
        if not username.isidentifier():
            return jsonify({"error": "El nombre de usuario no es valido"}), 409  # Código 409 para Conflicto

        # Insertar el nuevo usuario en la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, surname, username, password, email, code, role) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, surname, username, password, email, code, 1))
        conn.commit()
        conn.close()

        # Mandar correo con el codigo de validación
        send_validation_code(code, email)

        # Devolver una respuesta de éxito
        return jsonify({"mensaje": "Usuario agregado exitosamente y correo enviado."})

    except KeyError as e:
        # Manejar errores de datos faltantes en la solicitud JSON
        return jsonify({"error": f"Falta el campo {str(e)} en la solicitud"}), 400

    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500
  

@app.route("/validate", methods=["POST"])
def validate_user():
    """
    Validar un usuario en el sistema.

    Args:
        json (dict): JSON con los datos del formulario que contiene:
            - username (str): Nombre de usuario.
            - code (str): Código del usuario.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        # Obtener los datos del formulario desde el JSON de la solicitud
        data = request.json
        username = data['form']['username']
        user_code = data['form']['code']

        print("username", username)
        print("user_code", user_code)
    
       # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        
        # Obtener el código de confirmación de la cuenta del usuario desde la base de datos
        cursor.execute("SELECT id, code FROM users WHERE username = ?", (username,))
        datos = cursor.fetchone() 

        id, stored_code = datos
        
        if user_code == stored_code:

            # Si el código introducido por el usuario coincide con el almacenado en la base de datos
            # Actualizar la columna "validation" a True
            cursor.execute("UPDATE users SET validation = ? WHERE username = ?", (True, username))

            directorio = f"{username}_{id}"
                    
            crear_directorio_usuario(directorio)

            conn.commit()  # Guardar los cambios en la base de datos
            conn.close()  # Cerrar la conexión a la base de datos

            return jsonify({"mensaje": "Usuario validado correctamente."})
        
        else:
            conn.close()  # Cerrar la conexión a la base de datos
            return jsonify({"error": "Código de validación incorrecto."}), 400
        
    except KeyError as e:
        # Manejar errores de datos faltantes en la solicitud JSON
        return jsonify({"error": f"Falta el campo {str(e)} en la solicitud"}), 400
    
    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


@app.route("/login", methods=["POST"])
def log_user():
    """
    Iniciar sesión a un usuario dandole un token de autenticación.

    Args:
        json (dict): JSON con los datos del formulario que contiene:
            - username (str): Nombre de usuario.
            - password (str): Contraseña del usuario.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:

        # Obtener los datos del formulario desde el JSON de la solicitud
        data = request.json
        username = data['form']['username']
        password = data['form']['password']
        print(data)

        # Validar los datos del formulario (Agregar validaciones segun requisitos)
        if not username or not password:
            return jsonify({"error": "Todos los campos son obligatorios"}), 400
                

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Realizar la consulta para obtener la contraseña almacenada para el usuario proporcionado
        cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
        stored_data = cursor.fetchone()

        # Cerrar la conexión con la base de datos
        conn.close()

        # Comprobar si el usuario existe en la base de datos
        if stored_data:
            
            stored_password, stored_role = stored_data
            print(stored_password)
            print(stored_role)

            # Conectar a la base de datos
            conn = sqlite3.connect(database)
            cursor = conn.cursor()

            # CONSULTA OBTENET VALIDATION
            cursor.execute("SELECT validation FROM users WHERE username = ?", (username,))
            validation = cursor.fetchone()

            # Cerrar la conexión con la base de datos
            conn.close()
            validation = validation[0]
            print(validation)
             
            if validation == 0:
                return jsonify({"error": "Usuario no validado"}), 403
            
            #COMPROBAR QUE LA CONTRASEÑA ES CORRECTA
            if password == stored_password:

                # Incluir el rol en el token de acceso
                additional_claims = {"role": stored_role}
                access_token = create_access_token(identity=username, additional_claims=additional_claims)
                return jsonify(access_token=access_token), 200
            
            else:

                return jsonify({"error": "Credenciales inválidas"}), 401
        else:
            return jsonify({"error": "El usuario no existe"}), 404  # Código 404 para No encontrado
        
    except KeyError as e:
    # Manejar errores de datos faltantes en la solicitud JSON
        return jsonify({"error": f"Falta el campo {str(e)} en la solicitud"}), 400
    
    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


@app.route("/enviarCodigo", methods=["POST"])
def enviar_codigo():
    """
    Envia el código de validación al usuario dado.

    Args:
        json (dict): JSON con los datos del formulario que contiene:
            - username (str): Nombre de usuario.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:

        # Obtener los datos del formulario desde el JSON de la solicitud
        data = request.json
        user = data['user']
        print(data)

        # Validar los datos del formulario (Agregar validaciones segun requisitos)
        if not user:
            return jsonify({"error": "Todos los campos son obligatorios"}), 400
                
        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Realizar la consulta para obtener la contraseña almacenada para el usuario proporcionado
        cursor.execute("SELECT code, email FROM users WHERE username = ?", (user,))
        row = cursor.fetchone()

        # Verificar si se encontró un resultado
        if row is None:
            return jsonify({"error": "El usuario no existe"}), 404  # Código 404 para No encontrado
        
        code, email = row
        conn.close()

        # Mandar correo con el codigo de validación
        send_validation_code(code, email)    
        return jsonify({"mesage": "Código enviado"})   

    except KeyError as e:
    # Manejar errores de datos faltantes en la solicitud JSON
        return jsonify({"error": f"Falta el campo {str(e)} en la solicitud"}), 400
    
    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


@app.route("/forgotPasswd", methods=["POST"])
def forgot_passwd():
    """
    Comprueba y cambia la contraseña de un usuario que la haya olvidado.
    Usa el codigo de validación como 2FA enviandoselo al correo.

    Args:
        json (dict): JSON con los datos del formulario que contiene:
            - username (str): Nombre de usuario.
            - password (str): Nueva ontraseña del usuario.
            - code (str): Código de validación del usuario.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        # Obtener los datos del formulario desde el JSON de la solicitud
        data = request.json
        user = data['user']
        code = data['code']
        new_password = data['password']
        print(data)

        # Validar los datos del formulario
        if not user or not code or not new_password:
            return jsonify({"error": "Todos los campos son obligatorios"}), 400
                
        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Realizar la consulta para obtener el código y el correo almacenados para el usuario proporcionado
        cursor.execute("SELECT code FROM users WHERE username = ?", (user,))
        stored_code = cursor.fetchone()
        stored_code=stored_code[0]
        print(code, stored_code)
        # Verificar si se encontró un resultado
        if stored_code is None:
            return jsonify({"error": "El usuario no existe"}), 404  # Código 404 para No encontrado

        # Verificar si el código proporcionado coincide con el código almacenado
        if code != stored_code:
            return jsonify({"error": "El código proporcionado es incorrecto"}), 400

        # Actualizar la contraseña del usuario
        cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, user))
        conn.commit()
        conn.close()

        return jsonify({"mesage": "Contraseña cambiada con éxito"})

    except KeyError as e:
        # Manejar errores de datos faltantes en la solicitud JSON
        return jsonify({"error": f"Falta el campo {str(e)} en la solicitud"}), 400

    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


@app.route("/delete", methods=["GET"])
@jwt_required()
def delete_user():
    """
    Elimina un usuario del sistema, borrandolo de la base de datos
    e eliminando su directorio.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:

        current_user = get_jwt_identity()
        print(current_user)
       # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        id_user = cursor.fetchone()[0]  
      
        
        # Obtener todos los ID de los trabajos para el usuario
        cursor.execute("SELECT id_job FROM Recordatorios WHERE id_user = ?", (id_user,))
        rows = cursor.fetchall()

        # Cancelar cada uno de los trabajos programados
        for row in rows:
            job_id = row[0]
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

        # Eliminar recordatorios
        cursor.execute("DELETE FROM Recordatorios WHERE id_user = ?", (id_user,))

        # Eliminar cribados
        cursor.execute("DELETE FROM Cribados WHERE id_user = ?", (id_user,))

        # Obtener todos los id_lesion del seguimiento para el usuario
        cursor.execute("SELECT id FROM Seguimiento WHERE id_user = ?", (id_user,))
        id_lesion_rows = cursor.fetchall()

        for lesion in id_lesion_rows:

            id_lesion = lesion[0]
            # Eliminar historial
            cursor.execute("DELETE FROM Historial WHERE id_lesion = ?", (id_lesion,))


        # Eliminar seguimiento
        cursor.execute("DELETE FROM Seguimiento WHERE id_user = ?", (id_user,))

        # Eliminar el usuario de la tabla 'users'
        cursor.execute("DELETE FROM Users WHERE username = ?", (current_user,))

        conn.commit()  # Guardar los cambios en la base de datos


        directorio = f"{current_user}_{id_user}"

        # Eliminar el directorio del usuario
        user_directory = os.path.join('users', directorio)
        if os.path.exists(user_directory):
            shutil.rmtree(user_directory)

        return jsonify({"mensage": "User and related data deleted successfully"}), 200
           
    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        conn.rollback()
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        conn.rollback()
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500
    
    finally:
        conn.close()


#----  BODY HOME  ----------------------------------------------------------------------------------------------------------------


@app.route("/addResultado", methods=["POST"])
@jwt_required()
def add_Resultado():
    """
    Agregar un nuevo análisis del seguimiento a la base de datos.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - x (int): Coordenada X de la lesión.
            - y (int): Coordenada Y de la lesión.
            - lugar (str): Lugar de la lesión en el cuerpo.
            - body (str): Lugar de la lesión en el cuerpo(frontal/trasera).
            - imagen (str): Imagen en Base64.
            - predicciones (str): Array con las predicciones.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        current_user = get_jwt_identity()
        print(current_user)

        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id, role FROM users WHERE username = ?", (current_user,))
        usuario_data = cursor.fetchone()
        id_user, role_user = usuario_data
        print(id_user,role_user)

        if role_user == 0:
            print(data)
            id = data.get('id')

            if id is not None:
                id_user = id

                cursor.execute("SELECT username FROM users WHERE id = ?", (id_user,))
                current_user = cursor.fetchone()[0] 


        x = data.get('x')
        y = data.get('y')
        lugar = data.get('lugar')
        body = data.get('body')
        imagen = to_path64(data.get('imagen'),f"{current_user}_{id_user}")
        predicciones =  json.dumps(data.get('predicciones'))
        print(x,y,lugar,body,imagen,predicciones)


        # Insertar el nuevo marcador en la tabla seguimiento
        cursor.execute(f"INSERT INTO Seguimiento (id_user, x, y, lugar, body, imagen, predicciones) VALUES (?, ?, ?, ?, ?, ?, ?)", (id_user, x, y, lugar, body, imagen, predicciones))
        conn.commit()

        # Obtener el ID de la fila recién creada
        new_lesion_id = cursor.lastrowid

        fecha_actual = datetime.now().strftime("%d-%m-%Y")
        cursor.execute(f"INSERT INTO Historial (id_lesion, imagen, fecha, predicciones) VALUES (?, ?, ?, ?)", (new_lesion_id, imagen, fecha_actual, predicciones))
        conn.commit()

        # Cerrar la conexión con la base de datos
        conn.close()

        return jsonify({"mesage": "Resultado agregado correctamente"}), 200

    except Exception as e:
        print("Error al agregar el resultado:", e)
    
        # Eliminar la imagen del disco si existe
        if 'imagen' in locals():
            try:
                os.remove(imagen)
                print("Imagen eliminada del disco.")
            except Exception as e:
                print("Error al eliminar la imagen del disco:", e)

        return jsonify({"error": "Ocurrió un error al agregar el resultado"}), 500


@app.route("/addResultadoSimple", methods=["POST"])
@jwt_required()
def add_Resultado_simple():
    """
    Agregar un nuevo análisis de cribado a la base de datos del usuario.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - imagen (str): Imagen en Base64.
            - predicciones (str): Array con las predicciones.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        current_user = get_jwt_identity()
        print(current_user)

        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        id_user = cursor.fetchone()[0] 


        imagen = to_path64(data.get('imagen'),f"{current_user}_{id_user}")
        predicciones =  json.dumps(data.get('predicciones'))
        print(imagen,predicciones)


        # Insertar el nuevo cribado en la tabla cribados
        cursor.execute(f"INSERT INTO Cribados (id_user, imagen, predicciones) VALUES (?, ?, ?)", (id_user, imagen, predicciones))
        conn.commit()

        # Cerrar la conexión con la base de datos
        conn.close()

        return jsonify({"mesage": "Resultado guardado correctamente"}), 200

    except Exception as e:
        print("Error al guardar el resultado:", e)
    
        # Eliminar la imagen del disco si existe
        if 'imagen' in locals():
            try:
                os.remove(imagen)
                print("Imagen eliminada del disco.")
            except Exception as e:
                print("Error al eliminar la imagen del disco:", e)

        return jsonify({"error": "Ocurrió un error al guardar el resultado"}), 500


@app.route("/update", methods=["POST"])
@jwt_required()
def update_analisis(): 
    """
    Actualizar un análisis del seguimiento.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - id (Integer): Id de la lesión.
            - imagen (str): Imagen en Base64.
            - predicciones (str): Array con las predicciones.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """   
    conn = None  # Inicializar la variable conn
    try:
        current_user = get_jwt_identity()

        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        
        
        cursor.execute("SELECT id, role FROM users WHERE username = ?", (current_user,))
        usuario_data = cursor.fetchone()
        id_user, role_user = usuario_data
        print(id_user,role_user)

        if role_user == 0:
            print(data)
            id = data.get('paciente')

            if id is not None:
                id_user = id

                cursor.execute("SELECT username FROM users WHERE id = ?", (id_user,))
                current_user = cursor.fetchone()[0] 

        id_lesion = data.get('id')
        imagen = to_path64(data.get('imagen'),f"{current_user}_{id_user}")
        predicciones =  json.dumps(data.get('predicciones'))
        fecha_actual = datetime.now().strftime("%d-%m-%Y")
        print(id,predicciones,fecha_actual)


        # Insertar el nuevo marcador en la tabla correspondiente del usuario
        cursor.execute(f"UPDATE Seguimiento SET imagen = ?, predicciones = ? WHERE id = ?", (imagen, predicciones, id_lesion))
        conn.commit()


        cursor.execute(f"INSERT INTO Historial (id_lesion, imagen, fecha, predicciones) VALUES (?, ?, ?, ?)", (id_lesion, imagen, fecha_actual, predicciones))
        conn.commit()

        return jsonify({"mesage": "Resultado actualizado correctamente"})

    except sqlite3.Error as e:
        # Deshacer la transacción en caso de error
        conn.rollback()
        print(f"Error al actualizar los datos: {e}")
   
        # Eliminar la imagen del disco si existe
        if 'imagen' in locals():
            try:
                os.remove(imagen)
                print("Imagen eliminada del disco.")
            except Exception as e:
                print("Error al eliminar la imagen del disco:", e)

        return jsonify({"error": "Ocurrió un error al actualizar el resultado"}), 500
    
    finally:
        if conn:
            conn.close()


@app.route("/markers", methods=["POST"])
@jwt_required()
def obtener_markers():
    """
    Obtener todas las lesiones del seguimiento de la base de datos.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON que contiene:
            - id (int): Identificador del usuario si corresponde.

    Returns:
        dict: JSON que contiene:
            - id (int): Identificador de la lesión.
            - x (int): Coordenada X de la lesión.
            - y (int): Coordenada Y de la lesión.
            - lugar (str): Lugar de la lesión en el cuerpo.
            - body (str): Lugar de la lesión en el cuerpo(frontal/trasera).
            - imagen (str): Imagen en Base64.
            - probabilidad (str): Probabilidad de malignidad.
            - predicciones (str): Array con las predicciones.
            - color (str): Color asociado al riesgo.
    """
    try:
        # Obtener el usuario actual autenticado desde el token JWT
        usuario_actual = get_jwt_identity()
        
        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Obtener el rol del usuario actual
        cursor.execute("SELECT id, role FROM users WHERE username = ?", (usuario_actual,))
        usuario_data = cursor.fetchone()
        id_user, rol = usuario_data
        print(id_user,rol)

        if rol == 0:
            # Si el rol es 0, devolver la información del usuario con id = jsondata.id
            jsondata = request.get_json()

            if jsondata is not None:
                id = jsondata.get('id')

                if id is not None:
                    id_user = id

        print("buscando para: ",id_user)
        # Realizar la consulta SQL para obtener los marcadores del usuario actual
        cursor.execute("SELECT id, x, y, body, imagen, predicciones FROM Seguimiento where id_user=?",(id_user,))
        marcadores_usuario = cursor.fetchall()

        # Cerrar la conexión con la base de datos
        conn.close()

        # Verificar si se encontraron marcadores para el usuario
        if marcadores_usuario:
            # Formatear los resultados de la consulta
            markers = []
            for marker in marcadores_usuario:
                id, x, y, body, imagen_url, predicciones = marker

                # IMAGEN A BASE64
                with open(imagen_url, "rb") as img_file:
                    imagen_base64 = base64.b64encode(img_file.read()).decode('utf-8')

                # Obtener la probabilidad del primer elemento del array predicciones
                probabilidad = json.loads(predicciones)[0]

                predicciones_list = json.loads(predicciones)


                # ASIGNAR COLOR AL RIESGO
                color = colorRisk(float(probabilidad))
 
                # FORMATEAR MARKER
                markers.append({
                    "id": id,
                    "x": x,
                    "y": y,
                    "body": body,
                    "imagen": imagen_base64,
                    "probabilidad": probabilidad,
                    "predicciones": predicciones_list,
                    "color": color
                })

            # Convertir los resultados de la consulta a un formato JSON y devolverlos
            return jsonify({"markers": markers})
        else:
            return jsonify({"error": "No se encontraron marcadores para el usuario"}), 404

    except Exception as e:
        print("Error al obtener los marcadores:", e)
        return jsonify({"error": "Ocurrió un error al obtener los marcadores"}), 500


@app.route("/deleteMarker", methods=["POST"])
@jwt_required()
def delete_marker():
    """
    Eliminar una lesión del seguimiento a la base de datos.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - id (int): Identificador de la lesión.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        # Obtener el usuario actual
        current_user = get_jwt_identity()
        print(current_user)
        # Obtener el ID del marcador a eliminar del cuerpo de la solicitud
        data = request.json
        print(data)
        marker_id = data.get('id')

        if not marker_id:
            return jsonify({"error": "ID de marcador no proporcionado"}), 400

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        id_user = cursor.fetchone()[0] 

        # Obtener la ruta de la imagen del seguimiento antes de eliminarlo
        cursor.execute("SELECT imagen FROM Seguimiento WHERE id = ?", (marker_id,))
        row = cursor.fetchone()
        image_path = row[0] if row else None

        # Eliminar el marcador de la tabla Seguimiento
        cursor.execute(f"DELETE FROM Seguimiento WHERE id = ?", (marker_id,))
        conn.commit()

        # Obtener todas las rutas de las imágenes antes de eliminar los registros
        cursor.execute(f"SELECT imagen FROM Historial where id_lesion=?",(marker_id,))
        rows = cursor.fetchall()
        image_paths = [row[0] for row in rows]

        # Eliminar las filas de la tabla Historial
        cursor.execute("DELETE FROM Historial WHERE id_lesion = ?", (marker_id,))
        conn.commit() 

        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            print(f"Imagen eliminada: {image_path}")

        # Eliminar todas las imágenes del sistema de archivos
        for image_path in image_paths:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)

        # Cerrar la conexión con la base de datos
        conn.close()

        return jsonify({"mesage": "Marcador eliminado exitosamente"})
   
    except sqlite3.Error as e:
        # Deshacer la transacción en caso de error
        conn.rollback()

        return jsonify({"error": str(e)}), 500
   
    finally:
        # Cerrar la conexión con la base de datos
        conn.close()
   

@app.route("/historial", methods=["POST"])
@jwt_required()
def get_historial():
    """
    Conseguir el historial de una lesión de la base de datos.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - id (int): Identificador de la lesión.

    Returns:
        list: Una lista de diccionarios que contiene los detalles del historial.
            Cada diccionario tiene las siguientes claves:
            - id (int): Identificador único.
            - subId (int): Identificador secundario.
            - dia (int): Día del evento.
            - mes (int): Mes del evento.
            - año (int): Año del evento.
            - imagen (str): Imagen en formato base64.
            - probabilidad (str): Probabilidad calculada.
            - predicciones (str): Lista de predicciones.
            - color (str): Color asociado a la predicción.
    """
    try:

        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json

        id = data.get('id')

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Realizar la consulta SQL para obtener los marcadores del usuario actual
        cursor.execute("SELECT id, imagen, fecha, predicciones FROM Historial where id_lesion=?",(id,))
        marcadores_usuario = cursor.fetchall()

        # Cerrar la conexión con la base de datos
        conn.close()


        # Formatear los resultados de la consulta
        historial = []
        for registro in marcadores_usuario:
            subId, imagen_url, fecha, predicciones = registro

            # IMAGEN A BASE64
            with open(imagen_url, "rb") as img_file:
                imagen_base64 = base64.b64encode(img_file.read()).decode('utf-8')

            # Obtener la probabilidad del primer elemento del array predicciones
            probabilidad = json.loads(predicciones)[0]

            predicciones_list = json.loads(predicciones)

            fecha_objeto = datetime.strptime(fecha, '%d-%m-%Y')
            fecha_formateada = fecha_objeto.strftime('%d %b %Y')

            dia = fecha_formateada.split(' ')[0]
            mes = months_translations[fecha_formateada.split(' ')[1]]
            año = fecha_formateada.split(' ')[2]

            # ASIGNAR COLOR AL RIESGO
            color = colorRisk(float(probabilidad))

            # FORMATEAR MARKER
            historial.append({
                "id": id,
                "subId": subId,
                "dia": dia,
                "mes": mes,
                "año": año,
                "imagen": imagen_base64,
                "probabilidad": probabilidad,
                "predicciones": predicciones_list,
                "color": color
            })
            #print(fecha,probabilidad)
        # Convertir los resultados de la consulta a un formato JSON y devolverlos
        return jsonify({"historial": historial})


    except Exception as e:
        print("Error al obtener los marcadores:", e)
        return jsonify({"error": "Ocurrió un error al obtener historico"}), 500

@app.route("/delete_reg_historial", methods=["POST"])
@jwt_required()
def delete_reg__historial():
    """
    Eliminar un registro del historial de una lesión del seguimiento.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - subId (int): Identificador del registro historico de la lesión.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    conn = None  # Inicializar la variable conn
    try:
        current_user = get_jwt_identity()

        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json
        print(data)
        
        subId = data.get('subId')

        if not subId:
            return jsonify({"error": "Dato no proporcionado"}), 400

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()


        # Obtener la ruta de la imagen del registro antes de eliminarlo
        cursor.execute("SELECT imagen FROM Historial WHERE id = ?", (subId,))
        row = cursor.fetchone()
        image_path = row[0] if row else None

        # Eliminar registro de la tabla
        cursor.execute("DELETE FROM Historial WHERE id = ?", (subId,))
        conn.commit()

        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            print(f"Imagen eliminada: {image_path}")
    
        return jsonify({"mesage": "Registro eliminado exitosamente"})
    
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Error al eliminar el registro: {e}")
        return jsonify({"error": "Error al eliminar el registro"}), 500
    
    except OSError as e:
        print(f"Error al eliminar la imagen: {e}")
        return jsonify({"error": "Error al eliminar el registro"}), 500
    
    finally:
        if conn:
            conn.close()


#------     HOME MEDICOS     ---------------------------------------------------------------------------------------------------------------------


@app.route("/pacientes", methods=["GET"])
@jwt_required()
def obtener_pacientes():
    """
    Obtener todos los pacientes de la base de datos.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        dict: JSON que contiene:
            - id (int): Identificador del paciente.
            - username (str): Usuario del paciente.
            - name (str): Nombre del paciente.
            - surname (str): Apellido del paciente.
    """
    try:
        # Obtener el usuario actual autenticado desde el token JWT
        current_user = get_jwt_identity()
        claims = get_jwt()
        role = claims.get('role', None)
        #print(claims,current_user,role)

        # Verificar si el role del usuario es 0 (permitido)
        if role != 0:
            return jsonify({"error": "No autorizado"}), 403

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Realizar la consulta SQL para obtener todos los pacientes
        cursor.execute("SELECT id, username, name, surname FROM Users")
        pacientes = cursor.fetchall()

        # Cerrar la conexión con la base de datos
        conn.close()

        # Verificar si se encontraron pacientes
        if pacientes:
            # Formatear los resultados de la consulta
            pacientes_list = []
            for paciente in pacientes:
                id, username, name, surname = paciente
                pacientes_list.append({
                    "id": id,
                    "username": username,
                    "name": name,
                    "surname": surname
                })

            # Convertir los resultados de la consulta a un formato JSON y devolverlos
            return jsonify({"pacientes": pacientes_list})
        else:
            return jsonify({"error": "No se encontraron pacientes"}), 404

    except Exception as e:
        print("Error al obtener los pacientes:", e)
        return jsonify({"error": "Ocurrió un error al obtener los pacientes"}), 500


#------     CONFIGURACION     ---------------------------------------------------------------------------------------------------------------------


@app.route("/perfilImage", methods=["POST"])
@jwt_required()
def get_perfil_image():
    """
    Obtener la imagen de perfil del usuario.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON que contiene:
            - id (integer): Id del usuario si corresponde.

    Returns:
        dict: JSON que contiene:
            - imagen (str): Imagen codificada en Base64.
    """
    try:
        current_user = get_jwt_identity()

        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Obtener el rol del usuario actual
        cursor.execute("SELECT id, role FROM users WHERE username = ?", (current_user,))
        usuario_data = cursor.fetchone()
        id_user, rol = usuario_data

        if rol == 0:
            # Si el rol es 0, devolver la información del usuario con id = jsondata.id
            jsondata = request.get_json()

            if jsondata is not None:
                id = jsondata.get('id')

                if id is not None:
                    cursor.execute("SELECT username FROM users WHERE id = ?", (id,))
                    current_user = cursor.fetchone()[0]
                    id_user = id

        
        table_user_name = f"{current_user}_{id_user}"
        conn.close()

        directorio = os.path.join(app.config['DIRECTORIO_RAIZ'], 'users', table_user_name, 'perfil')

        # Verificar si el directorio existe
        if not os.path.exists(directorio):
            return jsonify({"error": "El directorio de imágenes no existe"}), 404
        
        # Leer los nombres de los archivos en el directorio
        for archivo in os.listdir(directorio):
            with open(os.path.join(directorio, archivo), "rb") as f:
                imagen_codificada = base64.b64encode(f.read()).decode("utf-8")

        
                return jsonify({"imagen": imagen_codificada})
    
        return jsonify({"error": "No se encontraron imágenes en el directorio"}), 404

    except Exception as e:

        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


@app.route("/setPerfilImage", methods=["POST"])
@jwt_required()
def set_perfil_image():
    """
    Actualizar la imagen del perfil del usuario.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON con los datos del formulario que contiene:
            - imagen (str): Imagen en Base64.
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.

    """
    try:
        current_user = get_jwt_identity()

        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        id_user = cursor.fetchone()[0] 
        table_user_name = f"{current_user}_{id_user}"
        conn.close()

        directorio = os.path.join(app.config['DIRECTORIO_RAIZ'], 'users', table_user_name, 'perfil')

        data = request.json
        if 'imagen' not in data:
            return jsonify({"error": "No image provided"}), 400

        imagen_codificada = data['imagen']

        # Crear el directorio si no existe
        if not os.path.exists(directorio):
            os.makedirs(directorio)

        # Decodificar la imagen y guardarla
        imagen_data = base64.b64decode(imagen_codificada)
        imagen_path = os.path.join(directorio, 'profile_image.png')  # Puedes cambiar el nombre y extensión del archivo según sea necesario

        with open(imagen_path, 'wb') as f:
            f.write(imagen_data)
    
        return jsonify({"message": "Image saved successfully"})

    except Exception as e:

        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500
       

@app.route("/userData", methods=["GET"])
@jwt_required()
def get_user_profile():
    """
    Obtener la información del perfil del usuario.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        dict: JSON que contiene:
            - name (str): Nombre del usuario.
            - surname (str): Apellido del usuario.
            - username (str): Nombre de usuario.
            - email (str): Correo electrónico del usuario.
    """
    try:
        current_user = get_jwt_identity()
        print("P ",current_user)

        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT name, surname, email FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"mensage": "User not found"}), 404

        user_data = {
            "name": user[0],
            "surname": user[1],
            "username": current_user,
            "email": user[2]
        }

        return jsonify({"data": user_data})
    
    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


@app.route("/userData", methods=["POST"])
@jwt_required()
def set_user_profile():
    """
    Actualizar la información del perfil del usuario.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON con los datos del formulario que contiene:.
            - name (str): Nombre del usuario.
            - surname (str): Apellido del usuario.
            - username (str): Nombre de usuario.
            - email (str): Correo electrónico del usuario.
        
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        current_user = get_jwt_identity()
        print(current_user)

        data = request.get_json()
        new_name = data.get('name')
        new_surname = data.get('surname')
        new_email = data.get('email')

        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Actualizar los datos del usuario
        cursor.execute("""
            UPDATE users
            SET name = ?, surname = ?, email = ?
            WHERE username = ?
        """, (new_name, new_surname, new_email, current_user))


        conn.commit()
        conn.close()

        return jsonify({"mensage": "Información del usuario actualizada."})
    
    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error al actualizar la información"}), 500
    

@app.route("/contactUs", methods=["POST"])
@jwt_required()
def sendMailToServer():
    """
    Enviar mensaje de contacto al correo del sistema.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON con los datos del formulario que contiene:
            - mensaje (str): Mensaje del usuario.
        
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        current_user = get_jwt_identity()

        data = request.get_json()
        msg = data.get('mensaje')

        send_basic_mail(current_user,"servidorstarup@gmail.com",msg,"")

        return jsonify({"mensage": "Mensaje enviado."})
    
    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error al actualizar la información"}), 500
 
@app.route("/contactUs_simple", methods=["POST"])
def sendMailToServer_simple():
    """
    Enviar mensaje de contacto al correo del sistema de un usuario anónimo.

    Args:
        dict: JSON con los datos del formulario que contiene:
            - email (str): Email del usuario.
            - user (str): Nombre del usuario.
            - mensaje (str): Mensaje del usuario.
        
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:
        data = request.get_json()

        email = data.get('email')
        user = data.get('user')
        msg = data.get('mensaje')

        send_basic_mail(user,"servidorstarup@gmail.com",msg,email)

        return jsonify({"mensage": "Mensaje enviado."})
    
    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error al enviar"}), 500
 

@app.route("/changePassword", methods=["POST"])
@jwt_required()
def changePasswd():
    """
    Actualizar la contraseña del usuario.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON con los datos del formulario que contiene:.
            - password (str): Nueva contraseña.
            - password2 (str): Confirmación de la nueva contraseña.
        
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """

    try:
        current_user = get_jwt_identity()

        # Obtener los datos del formulario desde el JSON de la solicitud.
        data = request.json
        passwd = data.get('password')
        passwd2 = data.get('password2')

        # Validar los datos del formulario (Agregar validaciones segun requisitos).
        if not passwd or not passwd2:
            return jsonify({"error": "Todos los campos son obligatorios"}), 400
        
        # Validar que las contraseñas coinciden
        if passwd != passwd2:
            return jsonify({"error": "Las contraseñas no coinciden"}), 400
        
        # Validar el formato de la contraseña
        if not re.match(r"^(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,16}$", passwd):
            return jsonify({"error": "La contraseña debe tener entre 8 y 16 caracteres, dígitos, minúsculas y mayúsculas."}), 400
        
        # Actualizar la contraseña del usuario.
        conn = sqlite3.connect(database)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password = ? WHERE username = ?", (passwd, current_user))

        conn.commit()
        conn.close()

        # Devolver una respuesta de éxito
        return jsonify({"mensage": "Contraseña actualizada."})

    except KeyError as e:
        # Manejar errores de datos faltantes en la solicitud JSON
        return jsonify({"error": f"Falta el campo {str(e)} en la solicitud"}), 400

    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500
  

#------ ANALISIS RAPIDO ---------------------------------------------------------------------------------------------------------------------


@app.route("/procesar_url", methods=['POST'])
@jwt_required()
def procesar_url():
    """
    Procesa una URL guardando la imagen en el servidor para posteriormente analizarla.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON con los datos del formulario que contiene:.
            - url (str): Dirección de imagen.
        
    Returns:
        dict: JSON que contiene:
            - imagen (str): Imagen codificada.
    """

    username = get_jwt_identity()

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
            # DESCARGAMOS IMAGEN A TEMP
            path =  to_pathWEB(response.content, username)

            with open(path, "rb") as f:
                imagen_codificada = base64.b64encode(f.read()).decode("utf-8")

            return jsonify({"imagen": imagen_codificada})
        
        except Exception as e:
            
            print(f"Se produjo un error: {str(e)}")
            return jsonify({"error": "Ocurrió un error durante el procesamiento de la imagen."}), 302
        
    
    else:
        return jsonify({"error": "Response.Status: La URL no existe."}), 300


#------- GALERIA -------------------------------------------------------------------------------------------------------------------

@app.route("/galeriaSimple", methods=["GET"])
@jwt_required()
def get_markers_Simple():
    """
    Obtener todas las lesiones de cribado de un usuario.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        dict: JSON que contiene:
            - id (int): Identificador de la lesión..
            - imagen (str): Imagen en Base64.
            - probabilidad (str): Probabilidad de malignidad.
            - predicciones (str): Array con las predicciones.
            - color (str): Color asociado al riesgo.
    """
    try:
        # Obtener el usuario actual autenticado desde el token JWT
        usuario_actual = get_jwt_identity()

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (usuario_actual,))
        id_user = cursor.fetchone()[0] 

        # Realizar la consulta SQL para obtener los cribados del usuario actual
        cursor.execute("SELECT id, imagen, predicciones  FROM Cribados WHERE id_user = ?", (id_user,))
        marcadores_usuario = cursor.fetchall()

        # Cerrar la conexión con la base de datos
        conn.close()

        # Verificar si se encontraron marcadores para el usuario
        if marcadores_usuario:
            # Formatear los resultados de la consulta
            markers = []
            for marker in marcadores_usuario:
                id, imagen_url, predicciones = marker

                # IMAGEN A BASE64
                with open(imagen_url, "rb") as img_file:
                    imagen_base64 = base64.b64encode(img_file.read()).decode('utf-8')

                # Obtener la probabilidad del primer elemento del array predicciones
                probabilidad = json.loads(predicciones)[0]

                predicciones_list = json.loads(predicciones)


                # ASIGNAR COLOR AL RIESGO
                color = colorRisk(float(probabilidad))
 
                # FORMATEAR MARKER
                markers.append({
                    "id": id,
                    "imagen": imagen_base64,
                    "probabilidad": probabilidad,
                    "predicciones": predicciones_list,
                    "color": color
                })

            # Convertir los resultados de la consulta a un formato JSON y devolverlos
            return jsonify({"markers": markers})
        else:
            return jsonify({"error": "No se encontraron marcadores para el usuario"}), 404

    except Exception as e:
        print("Error al obtener los marcadores:", e)
        return jsonify({"error": "Ocurrió un error al obtener los marcadores"}), 500

@app.route("/deleteSimple", methods=["POST"])
@jwt_required()
def delete_marker_Simple():
    """
    Eliminar una lesión del cribado del usuario.

    Args:
        Token (JWT): Token de autentificación.
        json (dict): JSON con los datos del formulario que contiene:
            - id (int): Identificador de la lesión.

    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.
    """
    try:

        # Obtener el ID del marcador a eliminar del cuerpo de la solicitud
        data = request.json
        print(data)
        marker_id = data.get('id')

        if not marker_id:
            return jsonify({"error": "ID de marcador no proporcionado"}), 400

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Obtener la ruta de la imagen del registro antes de eliminarlo
        cursor.execute("SELECT imagen FROM Cribados WHERE id = ?", (marker_id,))
        row = cursor.fetchone()
        image_path = row[0] if row else None

        # Eliminar el marcador de la tabla user_markers
        cursor.execute(f"DELETE FROM Cribados WHERE id = ?", (marker_id,))
        conn.commit()


        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            print(f"Imagen eliminada: {image_path}")


        # Cerrar la conexión con la base de datos
        conn.close()

        return jsonify({"mesage": "Marcador eliminado exitosamente"})
   
    except sqlite3.Error as e:
        # Deshacer la transacción en caso de error
        conn.rollback()

        return jsonify({"error": str(e)}), 500
   
    finally:
        # Cerrar la conexión con la base de datos
        conn.close()
   

@app.route("/galeria", methods=["GET"])
@jwt_required()
def obtener_galeria():
    """
    NO USADA. Obtener todas las imagenes del directorio del usuario.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        list: Una lista de diccionarios que contiene las imagenes.
            Cada diccionario tiene las siguientes claves:
                - imagen (str): Imagen en Base64.
    """
    try:
        
        print(get_jwt_identity())
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (get_jwt_identity(),))
        id_user = cursor.fetchone()[0] 
        table_user_name = f"{get_jwt_identity()}_{id_user}"

        conn.close()

        # Directorio de la galería de imágenes
        directorio = os.path.join(app.config['DIRECTORIO_RAIZ'], 'users', table_user_name, 'images')

        print(directorio)

        # Verificar si el directorio existe
        if not os.path.exists(directorio):
            return jsonify({"error": "El directorio de imágenes no existe"}), 404

        # Leer los nombres de los archivos en el directorio
        imagenes = []
        for archivo in os.listdir(directorio):
            with open(os.path.join(directorio, archivo), "rb") as f:
                imagen_codificada = base64.b64encode(f.read()).decode("utf-8")
                imagenes.append(imagen_codificada)
        
        return jsonify({"imagenes": imagenes})

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500

#------ CALENDARIO ---------------------------------------------------------------------------------------------------------------------


@app.route("/fechas", methods=["GET"])
@jwt_required()
def obtener_fechas():
    """
    Obtener los recordatorios de un usuario.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        list: Una lista de diccionarios que contiene los recordatorios.
            Cada diccionario tiene las siguientes claves:
                - id (str): Id del recordatorio.
                - recordatorio (str): Mensaje de recordatorio.
                - fecha (str): Fecha del recordatorio.
    """
    try:
        # Obtener el usuario actual autenticado desde el token JWT
        usuario_actual = get_jwt_identity()

        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ?", (usuario_actual,))
        id_user = cursor.fetchone()[0] 

        cursor.execute("SELECT id, recordatorio, fecha FROM Recordatorios where id_user=?",(id_user,))
        fechas_user = cursor.fetchall()

        # Cerrar la conexión con la base de datos
        conn.close()

        # Formatear los resultados de la consulta
        fechas = []
        for tupla in fechas_user:
            id, recordatorio, fecha = tupla
            
            # FORMATEAR MARKER
            fechas.append({
                "id": id,
                "recordatorio": recordatorio,
                "fecha": fecha
            })

        # Convertir los resultados de la consulta a un formato JSON y devolverlos
        return jsonify({"fechas": fechas})

    except sqlite3.Error as e:
        print("Error al obtener los recordatorios:", e.args[0])

    except Exception as e:
        print("Error al obtener los recordatorios:", e)
        return jsonify({"error": "Ocurrió un error al obtener los recordatorios"}), 500
    

@app.route("/addfecha", methods=["POST"])
@jwt_required()
def addfecha():
    """
    Añadir recordatorio y programar envio del mismo.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON con los datos del formulario que contiene:
            - id (Integer): Id del paciente si se requiere.
            - recordatorio (str): Mensaje de recordatorio.
            - fecha (str): Fecha del recordatorio.
        
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.

    """
    try:
        current_user = get_jwt_identity()
        #print(current_user)

        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json

        recordatorio = data.get('info')
        fecha = data.get('date')

        if not recordatorio or not fecha:
            return jsonify({"error": "Faltan datos necesarios"}), 400
        
        # Convertir la fecha a un objeto datetime
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%dT%H:%M')

        # Verificar si la fecha ya ha pasado
        if fecha_obj < datetime.now():
            return jsonify({"error": "La fecha del recordatorio ya ha pasado"}), 400

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        cursor.execute("SELECT id, email, role FROM users WHERE username = ?", (current_user,))
        usuario_data = cursor.fetchone()
        id_user, email, role_user = usuario_data

        if role_user == 0:
            id = data.get('id')

            if id is not None:
                id_user = id

                cursor.execute("SELECT email FROM users WHERE id = ?", (id_user,))
                email = cursor.fetchone()[0] 


        id_job = schedule_email(recordatorio, email, fecha)

        # Insertar el nuevo recordatorio en la tabla recordatorios
        cursor.execute(f"INSERT INTO Recordatorios (id_user, id_job, recordatorio, fecha) VALUES (?, ?, ?, ?)", (id_user, id_job, recordatorio, fecha))
        conn.commit()

        # Cerrar la conexión con la base de datos
        conn.close()

        return jsonify({"message": "Recordatorio agregado correctamente"}), 200

    except Exception as e:
        print("Error al agregar el recordatorio:", e)
    
        return jsonify({"error": "Ocurrió un error al agregar el recordatorio"}), 500


@app.route("/deletefecha", methods=["POST"])
@jwt_required()
def deletefecha():
    """
    Eliminar recordatorio y el trabajo de envio del mismo.

    Args:
        Token (JWT): Token de autentificación.
        dict: JSON que contiene:
            - id_recordatorio (str): Id del recordatorio.
        
    Returns:
        dict: Un diccionario con el mensaje de éxito o error.
            - mensaje (str): Mensaje de éxito o error.

    """
    try:
        # Obtener los datos del marcador desde el JSON de la solicitud
        data = request.json

        id_recordatorio = data.get('id')

        if not id_recordatorio:
            return jsonify({"error": "Faltan datos necesarios"}), 400

        # Conectar a la base de datos
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Obtener el ID del trabajo de la base de datos
        cursor.execute("SELECT id_job FROM Recordatorios WHERE id = ?", (id_recordatorio,))
        job_id = cursor.fetchone()

        if job_id is None:
            return jsonify({"error": "Recordatorio no encontrado"}), 404
        
        job_id = job_id[0]

        # Cancelar el trabajo programado
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        
        # Eliminar el recordatorio de la base de datos
        cursor.execute(f"DELETE FROM Recordatorios WHERE id = ?", (id_recordatorio,))
        conn.commit()

        # Cerrar la conexión con la base de datos
        conn.close()

        return jsonify({"message": "Registro eliminado correctamente"}), 200

    except Exception as e:
        print("Error al eliminar el registro:", e)
    
        return jsonify({"error": "Error al eliminar el registro"}), 500


#---- ESTADISTICAS   ------------------------------------------------------------------------------------------------------------------------------------------

@app.route("/estadisticas", methods=["POST"])
@jwt_required()
def get_estadisticas():
    """
    Obtener las estadísticas de un usuario.

    Args:
        Token (JWT): Token de autentificación.

    Returns:
        list: Una lista de diccionarios que contienen las estadísticas.

    """
    try:
        current_user = get_jwt_identity()
        
        conn = sqlite3.connect(database)
        cursor = conn.cursor()

        # Obtener el rol del usuario actual
        cursor.execute("SELECT id, role FROM users WHERE username = ?", (current_user,))
        usuario_data = cursor.fetchone()
        id_user, rol = usuario_data

        if rol == 0:
            # Si el rol es 0, devolver la información del usuario con id = jsondata.id
            jsondata = request.get_json()

            if jsondata is not None:
                id = jsondata.get('id')

                if id is not None:
                    id_user = id


        cursor.execute("SELECT lugar, predicciones FROM Seguimiento WHERE id_user=?",(id_user,))
        rows = cursor.fetchall()

        
        # Crear un diccionario para almacenar las estadísticas
        estadisticas = {
            "Cabeza": 0,
            "Cuello": 0,
            "Pecho": 0,
            "Torso": 0,
            "Espalda": 0,
            "Pelvis": 0,
            "Hombro Derecho": 0,
            "Brazo Derecho": 0,
            "Mano Derecha": 0,
            "Hombro Izquierdo": 0,
            "Brazo Izquierdo": 0,
            "Mano Izquierda": 0,
            "Pierna Derecha": 0,
            "Pie Derecho": 0,
            "Pierna Izquierda": 0,
            "Pie Izquierdo": 0,
            "otros": 0
        }

        categorias = {
            "Melanoma": estadisticas.copy(),
            "Nevus": estadisticas.copy(),
            "Carcinoma Basocelular": estadisticas.copy(),
            "Queratosis actínica": estadisticas.copy(),
            "Lesión benigna de queratosis": estadisticas.copy(),
            "Dermatofibroma": estadisticas.copy(),
            "Lesiones vasculares": estadisticas.copy(),
            "ERROR": 0
        }
        tiposLesion = ["Melanoma","Nevus","Carcinoma Basocelular","Queratosis actínica","Lesión benigna de queratosis","Dermatofibroma","Lesiones vasculares"]


        #Nuemro de lesiones en cada lugar
        for row in rows:
            lugar, predicciones = row
            if lugar in estadisticas.keys():
                print(lugar)
                estadisticas[lugar] += 1
            else:
                print(lugar)
                estadisticas["otros"] += 1

    
        #Nuemro de lesiones en cada lugar por tipo de lesion
        for row in rows:
            lugar, predicciones = row
            predicciones_list = json.loads(predicciones)

            # Convertir predicciones_list a un array numpy para facilitar el cálculo
            predicciones_array = np.array(predicciones_list[1:])

            # Encontrar el índice del valor máximo en predicciones_array
            indice_maximo = np.argmax(predicciones_array)
            
            # Asociar el índice máximo con el tipo de lesión correspondiente en tiposLesion
            tipo_lesion_asociado = tiposLesion[indice_maximo]

            if lugar in categorias[tipo_lesion_asociado].keys():
                categorias[tipo_lesion_asociado][lugar] += 1
            else:
                categorias["ERROR"] += 1

        #print(estadisticas,categorias)
        conn.close()
        
        return jsonify({"lesionesPorZona": estadisticas, "lesionesPorCategoria": categorias})
    
    except sqlite3.Error as e:
        # Manejar errores de la base de datos SQLite
        print("Error en la base de datos:", e)
        return jsonify({"error": "Error en la base de datos"}), 500

    except Exception as e:
        # Manejar otros errores inesperados
        print("Error inesperado:", e)
        return jsonify({"error": "Ocurrió un error inesperado"}), 500


#---- FUNCIONES AUXILIARES ------------------------------------------------------------------------------------------------------------------------------------

def generate_validation_code():
    # Genera una cadena de 5 dígitos numéricos aleatorios
    validation_code = ''.join(random.choice('0123456789') for _ in range(5))
    
    return validation_code


def send_basic_mail(remitente, email, text,remitente_mail):
 

    # Enviar correo electrónico al usuario
    subject = remitente    
    sender_email = "servidorstarup@gmail.com" 
    sender_password = "quph clcc udmh vowg"  # Contraseña para aplicaciones de Google

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = email

    # Parte HTML del mensaje
    html_part = MIMEText(text+"  "+remitente_mail, 'html')
    msg.attach(html_part)

    try:
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login(sender_email, sender_password)
        smtp_server.sendmail(sender_email, [email], msg.as_string())
        smtp_server.quit()
        return jsonify({"mensaje": "Usuario agregado exitosamente y correo enviado."})
    
    except smtplib.SMTPException as e:
        return jsonify({"error": f"Error al enviar el correo: {str(e)}"}), 500 


def send_validation_code(code, email):

    # Abrir HTML_Template
    with open('resources/template.html', 'r', encoding='utf-8') as file:
        email_template = file.read()

    # Variables del HTML
    email_template = email_template.replace('{codigo_de_validacion}', code)

    # Enviar correo electrónico al usuario
    subject = "Código de Validación"    
    sender_email = "servidorstarup@gmail.com" 
    sender_password = "quph clcc udmh vowg"  # Contraseña para aplicaciones de Google

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = email

    # Parte HTML del mensaje
    html_part = MIMEText(email_template, 'html')
    msg.attach(html_part)

    try:
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login(sender_email, sender_password)
        smtp_server.sendmail(sender_email, [email], msg.as_string())
        smtp_server.quit()
        return 0
    
    except smtplib.SMTPException as e:
        return jsonify({"error": f"Error al enviar el correo: {str(e)}"}), 500 


def send_recordatorio(recordatorio, email):

    # Abrir HTML_Template
    with open('/resources/template.html', 'r', encoding='utf-8') as file:
        email_template = file.read()

    # Variables del HTML
    email_template = email_template.replace('{codigo_de_validacion}', recordatorio)

    # Enviar correo electrónico al usuario
    subject = "Recordatorio"    
    sender_email = "servidorstarup@gmail.com" 
    sender_password = "quph clcc udmh vowg"  # Contraseña para aplicaciones de Google

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = email

    # Parte HTML del mensaje
    html_part = MIMEText(email_template, 'html')
    msg.attach(html_part)

    try:
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login(sender_email, sender_password)
        smtp_server.sendmail(sender_email, [email], msg.as_string())
        smtp_server.quit()
        return 0
    
    except smtplib.SMTPException as e:
        return e, 500 
    

def schedule_email(recordatorio, email, fecha):
    date_time_obj = datetime.strptime(fecha, '%Y-%m-%dT%H:%M')
    print(date_time_obj)
    return scheduler.add_job(send_recordatorio, 'date', run_date=date_time_obj, args=['Recordatorio: '+recordatorio, email]).id

# ARBOL DIRECTORIOS USUARIOS
def crear_directorio_usuario(username):

    # Ruta del directorio raíz del usuario
    directorio_raiz_usuario = os.path.join(app.config['DIRECTORIO_RAIZ'], "users", username)

    # Crear directorios 'images', 'temp' y 'perfil' si no existen
    for subdir in ["images", "temp", "perfil"]:
        directorio_subusuario = os.path.join(directorio_raiz_usuario, subdir)
        if not os.path.exists(directorio_subusuario):
            os.makedirs(directorio_subusuario)

    # Ruta del archivo perfil.webp en la raíz
    ruta_perfil_webp = os.path.join(app.config['DIRECTORIO_RAIZ'], "resources", "perfil.webp")

    # Ruta del directorio 'perfil' del usuario
    directorio_perfil_usuario = os.path.join(directorio_raiz_usuario, "perfil")

    # Copiar el archivo perfil.webp al directorio 'perfil' del usuario
    shutil.copyfile(ruta_perfil_webp, os.path.join(directorio_perfil_usuario, "profile_image.png"))


    # Retornar la ruta completa del directorio del usuario
    return directorio_raiz_usuario

# CREAR PATH
def to_path64(image64,username):

    content = image64.split(',')[1]
    timestamp = int(time.time())
    filename = f"image_{timestamp}.png"
    print(filename)
    path = os.path.join(app.config['DIRECTORIO_RAIZ'], 'users', username, 'images', filename)
    print(path)
    
    image_data = base64.b64decode(content)
        
    image = Image.open(BytesIO(image_data))
    print(image)
    image.save(path, format="png")

    return path

def colorRisk(probabilidad):
    
    if probabilidad <= 40:
        return "#00802b"
    
    if probabilidad >= 80:
        return "#ac3939"
    else:
        return "#ffc34d"

# GUARDAR IMAGEN URL PARA ANALISIS URL
def to_pathWEB(image, username):
    
    path = os.path.join(app.config['DIRECTORIO_RAIZ'],"users",username,"temp","imagen_decodificada.png")

    print(path)

    with open(path, "wb") as f:
        f.write(image)

    print("PATH", path)

    return path



#----------------------------------------------------------------------------------------------------------------------------------------

#if __name__ == "__main__":
#    app.run(host="0.0.0.0",port=5001)