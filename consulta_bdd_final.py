import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import psycopg2
import paho.mqtt.client as mqtt
import ssl
import uuid
from collections import deque

# Configuración de la bdd
db_config = {
    "host": "localhost",
    "database": "Autopicha",
    "user": "postgres",
    "password": "312005",
    "port": 5432
}

# Broker WebSocket seguro
BROKER = "broker.emqx.io"
PORT = 8084
WS_PATH = "/mqtt"

# Constantes de topics
RECIBIR_USUARIO = "UPV/PR2/2-08/recibir/usuario/robodk"
RECIBIR_PIZZA = "UPV/PR2/2-08/recibir/pizza/robodk"
HUMEDAD = "UPV/PR2/2-08/sensor/humedad"
TEMPERATURA = "UPV/PR2/2-08/sensor/temperatura"
NIVEL = "UPV/PR2/2-08/sensor/nivel"

#Cola para guardar los usuarios que piden pizza
user_queue = deque()

#Al mandar un topic, guardamos en la bdd la información asociada a este
def get_topic_id(conn, nombre_text):
    with conn.cursor() as cur:
        cur.execute("SELECT id_serial FROM topics WHERE nombre_text = %s", (nombre_text,))
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("INSERT INTO topics (nombre_text) VALUES (%s) RETURNING id_serial", (nombre_text,))
        return cur.fetchone()[0]

#Al recibir un dato de la placa de sensores, lo insertamos en la bdd con su información asociada
def insertar_dato(topic, valor):
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        topic_id = get_topic_id(conn, topic)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO datos_nevera (topic_id, valor_numeric) VALUES (%s, %s)",
                (topic_id, valor)
            )
        conn.commit()
        print(f"[OK] topic_id={topic_id} → {valor}")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR insert] {e}")
    finally:
        if conn:
            conn.close()

#Al recibir el tipo de pizza, insertamos en la bdd su información asociada
def insertar_o_actualizar_pizza(topic, mensaje):
    if not user_queue:
        print("[ERROR pizza] Cola vacía: no hay usuario al que asignar este pedido.")
        return

    #Sacamos el usuario más antiguo
    usuario = user_queue.popleft()
    print(f"[COLA] Desencolado usuario '{usuario}'. Cola restante={list(user_queue)}")


    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False

        #Obtenemos el topic_id y su cliente asociado:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id_cliente FROM cliente WHERE usuario = %s",
                (usuario,)
            )
            row = cur.fetchone()
            if not row:
                print(f"[ERROR pizza] No hay cliente con usuario={usuario}")
                conn.rollback()
                return
            cliente_id = row[0]

            #Insertamos el pedido obteniendo su id de vuelta
            cur.execute("""
                INSERT INTO pedido (estado, cliente)
                VALUES ('pendiente', %s)
                RETURNING id_pedido
            """, (cliente_id,))

            pedido_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO detalle_pedido (id_pedido, id_cliente, pizza, usuario)
                     VALUES (%s, %s, %s, %s)
            """, (pedido_id, cliente_id, mensaje, usuario))

        conn.commit()
        print(f"[OK PIZZA] Cliente {cliente_id} → pedido '{mensaje}' insertado.")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR pizza] {e}")
    finally:
        if conn:
            conn.close()

#Insertamos la informacion referente al cliente en la bdd
def insertar_o_actualizar_cliente(topic, mensaje):
    #Divide usuario y contraseña
    try:
        usuario, contrasenya = mensaje.split(":", 1)
    except ValueError:
        print(f"[ERROR formato] Mensaje inválido: {mensaje}")
        return

    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        topic_id = get_topic_id(conn, topic)
        with conn.cursor() as cur:
            #Verificar si ya existe un cliente con ese usuario y si existe lo actualiza
            cur.execute("SELECT id_cliente FROM cliente WHERE usuario = %s", (usuario,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE cliente SET contrasenya = %s, topic_id = %s WHERE usuario = %s",
                    (contrasenya, topic_id, usuario)
                )
                print(f"[ACTUALIZADO] Cliente '{usuario}' actualizado.")
            else:
                nuevo_id = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO cliente (id_cliente, usuario, contrasenya, topic_id) VALUES (%s, %s, %s, %s)",
                    (nuevo_id, usuario, contrasenya, topic_id)
                )
                print(f"[INSERTADO] Cliente '{usuario}' creado.")
        conn.commit()

        #Añadimos el usuario a la cola
        user_queue.append(usuario)
        print(f"[COLA] Usuario '{usuario}' encolado para pizza. Cola={list(user_queue)}")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR cliente] {e}")
    finally:
        if conn:
            conn.close()

#Gestiona el topic por el que se recibe la información
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    try:
        # Solo para pizzas
        if topic == RECIBIR_USUARIO:
            insertar_o_actualizar_cliente(topic, payload)
        elif topic in (TEMPERATURA, HUMEDAD, NIVEL):
            valor = float(payload)
            insertar_dato(topic, valor)
        elif topic == RECIBIR_PIZZA:
            insertar_o_actualizar_pizza(topic, payload)
    except Exception as e:
        print(f"[ERROR ws msg] {e}")

#Conexión a los brokers
if __name__ == "__main__":
    client = mqtt.Client(transport="websockets")
    client.on_message = on_message
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    client.connect(BROKER, PORT, keepalive=60)
    client.subscribe(RECIBIR_USUARIO)
    client.subscribe(RECIBIR_PIZZA)
    client.subscribe(TEMPERATURA)
    client.subscribe(HUMEDAD)
    client.subscribe(NIVEL)
    print("Esperando mensajes MQTT…")
    client.loop_forever()