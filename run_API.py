# run_server.py

from threading import Thread
from waitress import serve # type: ignore
from analyze import app as analyze_app
from user import app as user_app

if __name__ == "__main__":
    
    # CREAR HILO PARA EL PRIMER SERVICIO -> user_app
    user_thread = Thread(target=serve, args=(user_app,), kwargs={'host': '0.0.0.0', 'port': 5001})
    user_thread.start()  

    # Servir analyze_app en el hilo principal
    serve(analyze_app, host='0.0.0.0', port=5000)