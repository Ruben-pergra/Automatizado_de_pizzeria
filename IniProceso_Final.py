import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import threading
from robodk import *
from robolink import *
import time
from collections import deque
from queue import Queue
from queue import Empty
import ssl
import psycopg2
import paho.mqtt.client as mqtt
import os 

#Semáforos en true funciona la variable, en false no

#Semáforo para controlar la creación de una sola masa
mutex_crear = threading.Lock()
#Semáforo para controlar la creación de la masa
mutex_siguiente_ronda = threading.Lock()
#Semáforo para controlar el acceso a corte
mutex_corte = threading.Condition()
#Mutex para controlar la salida de la pizza del horno
mutex_recogida_pizza = threading.Lock()
#Mutex para controlar la espera de la caja en la cinta final si tiene una delante
mutex_espera_2 = threading.Lock()
#Mutex para controlar la espera de la caja en la cinta final si tiene una delante
mutex_espera_3 = threading.Lock()
#Mutex para controlar la espera de la caja en la cinta final si tiene una delante
mutex_espera_4 = threading.Lock()
#Mutex para controlar el numero de pizzas en el horno
mutex_horno = threading.Lock()
#Mutex para controlar el acceso a las colas donde guardamos los usuarios y las pizzas
mutex_usuario_pizza = threading.Lock()

#Definición de las variables de control de los semáforos
crear_masa_ctrl = True
Pizza_is_in_corte = True
recogida_pizza = True
siguiente_ronda = True
espera_2 = True
espera_3 = True
espera_4 = True

# Conexión a RoboDK
RDK = Robolink()

#Diccionario para guardar los objetos creados por el hilo de crear caja
resultado_hilos = {}

#Definición del control de pizzas en el horno y de la cola donde guardamos las que hay
MAX_PIZZAS_EN_HORNO = 1
horno = deque()

#Colas para guardar los pedidos de los clientes
cola_usuarios = Queue()
cola_pizzas   = Queue()

#Diccionario para verificar si el qr es el correcto
qr_events = {}

# Configuración de base de datos
db_config = {
    "host": "localhost",
    "database": "Autopicha",
    "user": "postgres",
    "password": "312005",
    "port": 5432
}

#Broker pagina web
BROKER_WS = "broker.emqx.io"
PORT_WS = 8084  # WSS port
TOPIC_USUARIO = 'UPV/PR2/2-08/recibir/usuario/robodk'
TOPIC_PIZZA = 'UPV/PR2/2-08/recibir/pizza/robodk'

#Broker arduino
BROKER_TCP   = "broker.hivemq.com"
PORT_TCP     = 1883
TOPIC_LEDS = 'UPV/PR2/2-08/control/leds'
TOPIC_SETA = 'UPV/PR2/2-08/seta/emergencia'
TOPIC_QR = 'UPV/PR2/2-08/qr/robodk'

#Variables de comunicación MQTT
DEFAULT_PEDIDO = 'Predeterminada'
PIZZA_QUESO = 'Pizza_David'
PIZZA_PEPERONI = 'Pizza_Ruben'
PIZZA_BACON = 'Pizza_Ricardo'
PIZZA_CHAMPIS = 'Pizza_Jordi'

# Parámetros de las cintas
MOVE_SPEED_MMS = -400  # Velocidad de las cintas en mm/s
REFRESH_RATE = 0.05  # Intervalo de actualización en segundos

#Definición de los programas de las estaciones
STATION_1_PREPROGRAM = 'PreProgPrensar'
STATION_1_POSTPROGRAM = 'PostProgPrensar'
PROGRAM_DEJAR_CUCHILLO = 'DejarCuchillo'
PROGRAM_COJER_PALA = 'CojerPala'
PROGRAM_COGER_PIZZA = 'Coger_pizza'
PROGRAM_POST_COGER_PIZZA = 'PostCoger_pizza'
PROGRAM_DEJAR_PALA = 'DejarPala'
PROGRAM_COJER_CUCHILLO = 'CojerCuchillo'
PROGRAM_CORTE = 'Corte'
PROGRAM_RETIRAR_PALA = 'Retirar_pala'
STATION_2_PROGRAM = 'Salsa2'

#-----------------------------------------------------------#
# Definición de las posiciones de la pizza en cada estación #
#-----------------------------------------------------------#

# Estación 1: Prensado
STATION_1_POSITION = -1370 

# Estación 2: Salsa
STATION_2_POSITION = -2000

# Estación 3: Ingredientes
STATION_3_PREPICK_POSITION = -2400
STATION_3_PICK_POSITION = -2500
STATION_3_PRE_QUESO_DROPPER = -800
STATION_3_QUESO_DROPPER = -650
STATION_3_BACON_DROPPER = -350
STATION_3_PEPPERONI_DROPPER = -50
STATION_3_CHAMPIS_DROPPER = 250
STATION_3_INGREDIENTS_POSITION = -50
STATION_3_QUESO_POSITION = -50
STATION_3_PRE_LAST_POSITION = 650
STATION_3_LAST_POSITION = 750
STATION_3_LAST_POSITION_Y = -2350

# Estación 4: Cocción
STATION_4_REPLACE_POSITION = -1250
STATION_4_PICK_POSITION = -10
STATION_4_POST_HORNO_POSITION = -430

#Estacion 5: Corte
STATION_5_BOX_POSITION = 100
STATION_5_TAPA_POSITION = 2160
STATION_5_BOX_CLOSED = 900

#Estacion 6: Recogida del pedido
STATION_6_PRE_PERSON_Y = 1800
STATION_6_PRE_PERSON_LAST_Y = 1920
STATION_6_PRE_PERSON_X = -150
STATION_6_FIRST_POSITION = -400
STATION_6_SECOND_POSITION = -880
STATION_6_THIRD_POSITION = -1350
STATION_6_LAST_POSITION = -1800

#Sistema de referencia de las pizzas
pizzas_ref = RDK.Item("Pizzas", ITEM_TYPE_FRAME)

# Función para verificar si el objeto está cerca de una posición específica
def is_at_station(part_pose, target_position, axis, tolerance=20):
    x, y, z = part_pose.Pos()
    if axis == 'X':
        return abs(x - target_position) <= tolerance
    elif axis == 'Y':
        return abs(y - target_position) <= tolerance
    elif axis == 'Z':
        return abs(z - target_position) <= tolerance
    return False

# Función para mover el objeto en la cinta y para poder rotarlo
def conveyor_move_object(part_item, movement, axis):
    part_pose = part_item.Pose()
    if axis == 'X':
        new_pose = transl(movement, 0, 0) * part_pose
    elif axis == 'Y':
        new_pose = transl(0, movement, 0) * part_pose
    elif axis == 'Z':
        new_pose = transl(0, 0, movement) * part_pose
    elif axis == 'RX':
        new_pose = part_pose * rotx(movement)
    elif axis == 'RY':
        new_pose = part_pose * roty(movement)
    elif axis == 'RZ':
        new_pose = part_pose * rotz(movement)

    part_item.setPose(new_pose)

# Función para ejecutar programas de RoboDK
def execute_station_program(program_name):
    program = RDK.Item(program_name, ITEM_TYPE_PROGRAM)
    if not program.Valid():
        print(f"Error: El programa {program_name} no existe.")
        return False

    program.RunProgram()
    while program.Busy():
        time.sleep(0.1)
    return True

#Función para crear una masa inicial
def crear_masa_ini(part_item, new_object_name):
    #Seleccionamos el objeto de la plantilla a copiar
    new_object_template = RDK.Item(new_object_name, ITEM_TYPE_OBJECT)
    if not new_object_template.Valid():
        print(f"Objeto plantilla '{new_object_name}' no encontrado.")
        return None

    new_object_template.Copy()
    if new_object_template is None or not new_object_template.Valid():
        print(f"Fallo al copiar '{new_object_name}'.")
        return None
    
    #Lo pegamos en una nueva variable
    new_part=RDK.Paste()
    if new_part is None or not new_part.Valid():
        print(f"Fallo al pegar '{new_object_name}'.")
        return None
    
    #Le decimos donde queremos que se pegue y le damos un nombre dinámico para poder diferenciarla
    new_part.setParent(pizzas_ref)
    new_name = f"{new_object_name}_inst_{int(time.time() * 1000)}"
    new_part.setName(new_name)
    new_part.setPose(part_item.Pose())
    new_part.setVisible(True)
    return new_part

#Función para crear una caja, misma lógica que crear_masa_ini pero con la caja y la tapa
def crear_caja_ini(part_item, new_object_name):
    time.sleep(REFRESH_RATE + 0.05)
    new_object_template = RDK.Item(new_object_name, ITEM_TYPE_OBJECT)
    if not new_object_template.Valid():
        print(f"Objeto plantilla '{new_object_name}' no encontrado.")
        return None

    new_object_template.Copy()
    if new_object_template is None or not new_object_template.Valid():
        print(f"Fallo al copiar '{new_object_name}'.")
        return None
    
    new_part=RDK.Paste()
    if new_part is None or not new_part.Valid():
        print(f"Fallo al pegar '{new_object_name}'.")
        return None
    
    new_part.setParent(pizzas_ref)
    new_name = f"{new_object_name}_inst_{int(time.time() * 1000)}"
    new_part.setName(new_name)
    new_part.setPose(part_item.Pose())
    new_part.setVisible(True)
    
    tapa = RDK.Item('tapa_pizza', ITEM_TYPE_OBJECT)
    if tapa is None or not tapa.Valid():
        print(f"Error: No se encontró la tapa para la caja.")
        return None
    
    tapa.Copy()
    if tapa is None or not tapa.Valid():
        print(f"Fallo al copiar '{tapa}'.")
        return None
    
    tapa_new=RDK.Paste()
    if tapa_new is None or not tapa_new.Valid():
        print(f"Fallo al pegar '{tapa_new}'.")
        return None
    tapa_new.setParent(pizzas_ref)
    new_tapa_name = f"tapa_pizza_inst_{int(time.time() * 1000)}"
    tapa_new.setName(new_tapa_name)
    tapa_new.setPose(tapa.Pose())
    tapa_new.setVisible(True)

    #Mover la caja a la posición de la estación 5
    while not is_at_station(new_part.Pose(), STATION_5_BOX_POSITION, axis='X', tolerance=0) and not is_at_station(tapa_new.Pose(), STATION_5_TAPA_POSITION, axis='X', tolerance=0):
        conveyor_move_object(new_part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
        conveyor_move_object(tapa_new, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
        time.sleep(REFRESH_RATE)

    #Guardamos el resultado de cada parte de la caja en el diccionario
    resultado_hilos["Tapa"] = tapa_new
    resultado_hilos["hilo1"] = new_part

    return new_part

# Función para reemplazar el objeto en la estación, mimsa lógica que crear_masa_ini pero borrando el objeto antiguo
def replace_object(part_item, new_object_name):
    new_object_template = RDK.Item(new_object_name, ITEM_TYPE_OBJECT)
    if not new_object_template.Valid():
        print(f"Objeto plantilla '{new_object_name}' no encontrado.")
        return None

    new_object_template.Copy()
    if new_object_template is None or not new_object_template.Valid():
        print(f"Fallo al copiar '{new_object_name}'.")
        return None
    
    new_part=RDK.Paste()
    if new_part is None or not new_part.Valid():
        print(f"Fallo al pegar '{new_object_name}'.")
        return None
    
    new_part.setParent(pizzas_ref)
    new_name = f"{new_object_name}_inst_{int(time.time() * 1000)}"
    new_part.setName(new_name)
    new_part.setPose(part_item.Pose())
    new_part.setVisible(True)


    RDK.Delete(part_item)
    return new_part

# Función para ejecutar el programa de quitar la pala en paralelo a la caída de la pizza de esta
def Execute_quitar_pala(program_name):
    time.sleep(0.3)
    if not execute_station_program(program_name):
        print(f"Error al ejecutar el programa {program_name}.")

#Función para dejar caer la pizza de la pala simulando una animación
def Rotar_pizza (part_item):
    while not (is_at_station(part_item.Pose(), 15, axis='Z', tolerance=15) and is_at_station(part_item.Pose(), 705, axis='Y', tolerance=15)):
        conveyor_move_object(part_item, -15, axis='Z')
        conveyor_move_object(part_item, 30, axis='Y')
        time.sleep(REFRESH_RATE)

    while not (is_at_station(part_item.Pose(), -95, axis='Z', tolerance=5) and is_at_station(part_item.Pose(), 685, axis='Y', tolerance=5)):
        if not is_at_station(part_item.Pose(), -95, axis='Z', tolerance=5):
            conveyor_move_object(part_item, -10, axis='Z')
        if not is_at_station(part_item.Pose(), 685, axis='Y', tolerance=5):
            conveyor_move_object(part_item, -5, axis='Y')
        conveyor_move_object(part_item, 0.05550147, axis='RX')
    time.sleep(REFRESH_RATE)

# Función para manejar los mensajes de los topics
def on_message_tcp(client_tcp, userdata, msg):
    mensaje = msg.payload.decode()
    topic   = msg.topic

    if topic == TOPIC_QR:
        #Guardamos el usuario que solicita el qr
        usuario_qr = mensaje
        #Establecemos el evento que se tiene que dar para desaparecer la pizza con el qr
        event = qr_events.get(usuario_qr)
        if event:
            print(f"QR recibido para {usuario_qr}, desbloqueando estación 6")
            event.set()
        else:
            print(f"QR de {usuario_qr} sin pedido activo, ignorado")
    elif topic == TOPIC_SETA:
        print(f"[EMERGENCIA] Recibido {mensaje} en {TOPIC_SETA}, cerrando aplicación.")
        try:
            client_tcp.disconnect()
        except:
            pass
        os._exit(0)

# Función para manejar la suscripción a los topics
def on_connect_ws(client, userdata, flags, rc):
    print("Conectado con código:", rc)
    client.subscribe(TOPIC_USUARIO)
    client.subscribe(TOPIC_PIZZA)

# Función para manejar los mensajes de los topics WebSocket
def on_message_ws(client, userdata, msg):
    mensaje = msg.payload.decode()
    topic   = msg.topic
    print(f"Mensaje recibido en {topic}: {mensaje}")

    if topic == TOPIC_USUARIO and ":" in mensaje:
        usuario, _ = mensaje.split(":", 1)
        with mutex_usuario_pizza:
            cola_usuarios.put(usuario)

    elif topic == TOPIC_PIZZA:
        with mutex_usuario_pizza:
            cola_pizzas.put(mensaje)

#Función para mandar a la placa el estado que tiene que poner en los leds según el estado y la actualización de este en la bdd, si es la primera vez que se actualiza el estado obtiene el id del pedido
def actualizar_estado(usuario,estado, identificador_pedido):
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        with conn.cursor() as cur:
            # 1) Obtener id_cliente
            cur.execute(
                "SELECT id_cliente FROM cliente WHERE usuario = %s",
                (usuario,)
            )
            row = cur.fetchone()
            if not row:
                print(f"[ERROR] Usuario '{usuario}' no encontrado.")
                conn.rollback()
                return []
            id_cliente = row[0]

            # 2) Elegir EL pedido más reciente (fecha con hora)
            if identificador_pedido is None:
                cur.execute(
                    """
                    SELECT id_pedido
                      FROM public.pedido
                     WHERE cliente = %s
                     ORDER BY fecha DESC
                     LIMIT 1
                    """,
                    (id_cliente,)
                )
                row = cur.fetchone()
                if not row:
                    # No hay pedidos
                    conn.rollback()
                    return []
                id_pedido = row[0]
            else:
                # Usamos directamente el identificador pasado
                id_pedido = identificador_pedido
                #Verificar que existe y pertenece al cliente:
                cur.execute(
                    """
                    SELECT 1
                      FROM public.pedido
                     WHERE id_pedido = %s
                       AND cliente = %s
                    """,
                    (id_pedido, id_cliente)
                )
                if not cur.fetchone():
                    print(f"[ERROR] Pedido '{id_pedido}' no válido para usuario '{usuario}'.")
                    conn.rollback()
                    return []

            # 3) Actualizar pedido
            cur.execute(
                "UPDATE public.pedido SET estado = %s WHERE id_pedido = %s",
                (estado, id_pedido)
            )
            # 4) Y su pizza_terminada asociada
            cur.execute(
                "UPDATE public.pizza_terminada SET estado = %s WHERE pedido = %s",
                (estado, id_pedido)
            )

        conn.commit()
        return id_pedido

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"[ERROR actualizar_estado] {e}")
        return []
    finally:
        if conn:
            conn.close()

#Corre la masa por la cinta, activa la prensa y permite la creación de una nueva masa
def run_station_1(part):
    global crear_masa_ctrl

    while not is_at_station(part.Pose(), STATION_1_POSITION, axis='Y'):
        conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
        time.sleep(REFRESH_RATE)
    if execute_station_program(STATION_1_PREPROGRAM):
        part = replace_object(part, 'pizza_masa_prensada')
        if part is None:
            print("Error al reemplazar la masa tras el prensado.")
            return None
    else:
        print("Error al ejecutar el programa de prensado.")
        return None
    if not execute_station_program(STATION_1_POSTPROGRAM): return

    with mutex_crear:
        crear_masa_ctrl = True
    return part

#Mueve la masa por la cinta hasta la estación 2, ejecuta el programa de salsa y la deja en la cinta de ingredientes
def run_station_2(part):

    while not is_at_station(part.Pose(), STATION_2_POSITION, axis='Y'):
        conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
        time.sleep(REFRESH_RATE)


    if execute_station_program(STATION_2_PROGRAM):
        part = replace_object(part, 'pizza_tomate')
        if part is None:
            print("Error al reemplazar la masa tras poner salsa.")
            return None
    else:
        print("Error al ejecutar el programa de salsa.")
        return None

    while not is_at_station(part.Pose(), STATION_3_PREPICK_POSITION, axis='Y'):
        conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
        time.sleep(REFRESH_RATE)

    #Mover la pizza en cinta circular
    while (not (is_at_station(part.Pose(), STATION_3_PICK_POSITION, axis='Y') and is_at_station(part.Pose(), STATION_3_PRE_QUESO_DROPPER, axis='X'))):
        if not is_at_station(part.Pose(), STATION_3_PICK_POSITION, axis='Y'):
            conveyor_move_object(part, -200 * REFRESH_RATE, axis='Y')
        if not is_at_station(part.Pose(), STATION_3_PRE_QUESO_DROPPER, axis='X'):
            conveyor_move_object(part, 200 * REFRESH_RATE, axis='X') 
        time.sleep(REFRESH_RATE)

    return part

#Mueve la masa por los ingredientes eligiendo cual tiene que poner según el pedido del usuario, si no hay pedido se pone queso
def run_station_3(part, pedido_usuario, identificador_pedido):
    queso = RDK.Item("queso", ITEM_TYPE_OBJECT)
    bacon = RDK.Item("bacon", ITEM_TYPE_OBJECT)
    pepperoni = RDK.Item("pepperoni", ITEM_TYPE_OBJECT)
    champis = RDK.Item("champis", ITEM_TYPE_OBJECT)

    while not is_at_station(part.Pose(), STATION_3_QUESO_DROPPER, axis='X'):
        conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
        time.sleep(REFRESH_RATE)

    queso_part = crear_masa_ini(queso, 'queso')
    #Cae el queso
    while not is_at_station(queso_part.Pose(), STATION_3_QUESO_POSITION, axis='Z'):
        conveyor_move_object(queso_part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Z')
        time.sleep(REFRESH_RATE)
    part = replace_object(part, 'pizza_queso_cruda')
    RDK.Delete(queso_part)

    #Si se ha pedido una pizza distinta a la de queso le pone otro ingrediente además de este
    if pedido_usuario != DEFAULT_PEDIDO:
        #Obtengo solo el tipo de pizza que se ha pedido
        _, pizza_usada = pedido_usuario.split(":", 1)
        if pizza_usada == PIZZA_BACON:
            #Parar pizza en el bacon
            while not is_at_station(part.Pose(), STATION_3_BACON_DROPPER, axis='X'):
                conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
                time.sleep(REFRESH_RATE)
            bacon_part = crear_masa_ini(bacon, 'bacon')
            #Cae el bacon
            while not is_at_station(bacon_part.Pose(), STATION_3_QUESO_POSITION, axis='Z'):
                conveyor_move_object(bacon_part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Z')
                time.sleep(REFRESH_RATE)
            part = replace_object(part, 'pizza_bacon_cruda')
            RDK.Delete(bacon_part)
        elif pizza_usada == PIZZA_PEPERONI:
            #Parar pizza en el pepperoni
            while not is_at_station(part.Pose(), STATION_3_PEPPERONI_DROPPER, axis='X'):
                conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
                time.sleep(REFRESH_RATE)
            pepperoni_part = crear_masa_ini(pepperoni, 'pepperoni')
            #Cae el pepperoni
            while not is_at_station(pepperoni_part.Pose(), STATION_3_QUESO_POSITION, axis='Z'):
                conveyor_move_object(pepperoni_part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Z')
                time.sleep(REFRESH_RATE)
            part = replace_object(part, 'pizza_pepperoni_cruda')
            RDK.Delete(pepperoni_part)

        elif pizza_usada == PIZZA_CHAMPIS:
            #Parar pizza en los champis
            while not is_at_station(part.Pose(), STATION_3_CHAMPIS_DROPPER, axis='X'):
                conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
                time.sleep(REFRESH_RATE)
            champis_part = crear_masa_ini(champis, 'champis')
            #Caen los cahmpis
            while not is_at_station(champis_part.Pose(), STATION_3_QUESO_POSITION, axis='Z'):
                conveyor_move_object(champis_part, MOVE_SPEED_MMS * REFRESH_RATE, axis='Z')
                time.sleep(REFRESH_RATE)
            part = replace_object(part, 'pizza_champis_cruda')
            RDK.Delete(champis_part)

    while not is_at_station(part.Pose(), STATION_3_PRE_LAST_POSITION, axis='X'):
        conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
        time.sleep(REFRESH_RATE)

    #Movimiento de la pizza en cinta circular
    while not is_at_station(part.Pose(), STATION_3_PRE_LAST_POSITION, axis='X'):
        conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
        time.sleep(REFRESH_RATE)
    while (not (is_at_station(part.Pose(), STATION_3_LAST_POSITION_Y, axis='Y') and is_at_station(part.Pose(), STATION_3_LAST_POSITION, axis='X'))):
        if not is_at_station(part.Pose(), STATION_3_LAST_POSITION_Y, axis='Y'):
            conveyor_move_object(part, 200 * REFRESH_RATE, axis='Y')
        if not is_at_station(part.Pose(), STATION_3_LAST_POSITION, axis='X'):
            conveyor_move_object(part, 200 * REFRESH_RATE, axis='X') 
        time.sleep(REFRESH_RATE)
    
    #Si es una pizza pedida por usuario actualiza el estado
    if pedido_usuario != DEFAULT_PEDIDO:
        client_tcp.publish(TOPIC_LEDS, "HORNO")
        usuario, _ = pedido_usuario.split(":", 1)
        actualizar_estado(usuario, "HORNO", identificador_pedido)
    return part

#Mueve la pizza al horno, la cocina y la deja en la cinta para que el usuario la recoja
def run_station_4(part):
    global siguiente_ronda
    caja_con_tapa =RDK.Item('caja_con_tapa', ITEM_TYPE_OBJECT)

    #Asociamos la pizza cruda con su respectiva cocinada
    COOKED_OBJECT_MAP = {
        'pizza_bacon_cruda': 'pizza_bacon_cocinada',
        'pizza_champis_cruda': 'pizza_champis_cocinada',
        'pizza_pepperoni_cruda': 'pizza_pepperoni_cocinada',
        'pizza_queso_cruda': 'pizza_queso_cocinada'
    }

    #Cambiamos el tipo de pizza a cocinada
    raw_name = part.Name().split('_inst_')[0] 
    cooked_name = COOKED_OBJECT_MAP.get(raw_name)

    if not cooked_name:
        print(f"Error: No se encontró versión cocinada para {part.Name()}")
        return

    while not is_at_station(part.Pose(), STATION_4_REPLACE_POSITION, axis='Y'):
        conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
        time.sleep(REFRESH_RATE)
    time.sleep(REFRESH_RATE)

    #Para darle tiempo al corte
    time.sleep(3)

    part = replace_object(part, cooked_name)
    time.sleep(REFRESH_RATE)

    #Permitimos la creación de más pizzas
    with mutex_siguiente_ronda:
        siguiente_ronda = True
    
    #Guardamos el nombre del hilo en ejecución de esta parte
    nombre = threading.current_thread().name
    with mutex_horno:
        #Establecemos una condición para esperar si el horno está lleno
        cond_pizza = threading.Condition(mutex_horno)
        #Si hay más pizzas en el horno que las permitidas, despertamos la más antigua y la sacamos de la cola
        if len(horno) >= MAX_PIZZAS_EN_HORNO:
            _, cond_antigua = horno.popleft()
            cond_antigua.notify() 
        #ñadimos la nueva pizza a la cola del horno
        horno.append((nombre, cond_pizza))
        #Esperamos a que llegue otra pizza
        cond_pizza.wait()

    while not is_at_station(part.Pose(), STATION_4_POST_HORNO_POSITION, axis='Y'):
        conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
        time.sleep(REFRESH_RATE)

    while not is_at_station(part.Pose(), STATION_4_PICK_POSITION, axis='Y'):
        with mutex_recogida_pizza:
            if recogida_pizza:
                conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
                time.sleep(REFRESH_RATE)
    
    #Esperamos a que salga la anterior pizza de corte
    with mutex_corte:
        while not Pizza_is_in_corte:
            mutex_corte.wait()

    #Este hilo se encarga de mover las cajas a su sitio en estacion 5
    time.sleep(REFRESH_RATE + 0.1)
    hilo_crear_caja = threading.Thread(target=crear_caja_ini, daemon=True, args=(caja_con_tapa, "caja_con_tapa"))
    hilo_crear_caja.start()

    return part

#Coge la pizza, le hace el corte y cierra la caja
def run_station_5(part):
    global Pizza_is_in_corte
    global recogida_pizza

    #Dejamos que la pizza salga del horno para coordinar la recogida
    with mutex_recogida_pizza:
        recogida_pizza = False

    #Establecemos la posición de la pizza tras establecerle padres distintos
    pose_de_pizza_rotada = transl(98, 585, 85) * rotx(-0.61) * roty(0) * rotz(0)
    pose_de_pizza_en_pala = transl(5, -204, 18)

    # Programa : Coger pala
    if not execute_station_program(PROGRAM_COJER_PALA): return

    # Programa : Coger pizza y pegarla a la pala
    if execute_station_program(PROGRAM_COGER_PIZZA):
        pala = RDK.Item('palapizza[1]', ITEM_TYPE_OBJECT)
        if pala.Valid():
            part.setParent(pala)
            part.setPose(pose_de_pizza_en_pala)
        else:
            print("Error: No se encontró la pala para pegar la pizza.")
            return
    else:
        print(f"Error al ejecutar el programa {PROGRAM_COGER_PIZZA}")
        return
    with mutex_recogida_pizza and mutex_corte:
        Pizza_is_in_corte = False
        recogida_pizza = True

    # Programa : Dejar pizza
    if not execute_station_program(PROGRAM_POST_COGER_PIZZA): return
   
    # Despegar pizza de la pala
    part.setParent(pizzas_ref)
    part.setPose(pose_de_pizza_rotada)

    # Retirar pala
    hilo_pala = threading.Thread(target=Execute_quitar_pala, daemon=True, args=(PROGRAM_RETIRAR_PALA,))
    hilo_pala.start()

    # Girar pizza
    hilo_rotar = threading.Thread(target=Rotar_pizza, daemon=True, args=(part,))
    hilo_rotar.start()

    #Esperar a q terminen los hilos
    hilo_pala.join()
    hilo_rotar.join()

    # Programa : Dejar pala
    if not execute_station_program(PROGRAM_DEJAR_PALA): return

    # Programa : Coger cuchillo
    if not execute_station_program(PROGRAM_COJER_CUCHILLO): return

    # Programa : Corte
    if not execute_station_program(PROGRAM_CORTE): return

    # Programa : Dejar cuchillo otra vez
    if not execute_station_program(PROGRAM_DEJAR_CUCHILLO): return

    #Quitamos del diccionario las cajas y tapas que hemos creado
    nueva_caja = resultado_hilos.pop("hilo1")
    tapa_caja = resultado_hilos.pop("Tapa")

    #Combinamos la pizza a la caja en un solo objeto
    objetos_a_combinar = [nueva_caja,part]
    combinado_caja_pizza = RDK.MergeItems(objetos_a_combinar)
    combinado_caja_pizza.setName("Caja_pizza_combinada")

    if combinado_caja_pizza is None or not combinado_caja_pizza.Valid():
        print("Error al combinar la pizza y la caja\n")
        return None
    #Dejamos que entre una nueva pizza al corte
    with mutex_corte:
        Pizza_is_in_corte = True
        mutex_corte.notify_all()

    #Animación de cerrado de la caja
    for i in range(18):
        if i ==1:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 30, -20) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==2:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, -10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==3:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, -20) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==4:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, -10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==5:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, -10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==6:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, -10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==7:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 50, -10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==8:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 50, 0) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==9:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, 0) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==10:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 50, -10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==11:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 50, 0) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==12:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, 0) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==13:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, 10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==14:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 50, 0) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==15:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 40, 10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==16:
            conveyor_move_object(tapa_caja, 0.0959931, axis='RX')
            conveyor_move_object(combinado_caja_pizza, 25, axis='Y')
            new_pose = transl(0, 45, 10) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)
        if i ==17:
            conveyor_move_object(tapa_caja, 0.0349066, axis='RX')
            new_pose = transl(0, 10, 0) * tapa_caja.Pose()
            tapa_caja.setPose(new_pose)
            time.sleep(REFRESH_RATE)

    #Combinamos la tapa y la caja con la pizza en un solo objeto
    combinar_caja = [combinado_caja_pizza,tapa_caja]
    combinado_caja = RDK.MergeItems(combinar_caja)
    combinado_caja.setName("Caja_entera")
    if combinado_caja is None or not combinado_caja.Valid():
        print("Error al combinar la caja y la tapa\n")
        return None
    return combinado_caja
    
#Mueve la pizza por la cinta final para su recogida, si no ha sido pedida, la borra al tiempo
def run_station_6(part, pedido_usuario, identificador_pedido):
    global espera_2
    global espera_3
    global espera_4

    #Si la pizza ha sido pedida, actualiza el estado
    if pedido_usuario != DEFAULT_PEDIDO:
        client_tcp.publish(TOPIC_LEDS, "LISTA")
        usuario, _ = pedido_usuario.split(":", 1)
        actualizar_estado(usuario, "LISTA", identificador_pedido)

    #Preparamos el event si es pedido real
    if pedido_usuario != DEFAULT_PEDIDO:
        event = threading.Event()
        qr_events[usuario] = event
    else:
        event = None

    while not is_at_station(part.Pose(), STATION_6_PRE_PERSON_Y, axis='Y'):
        conveyor_move_object(part, -MOVE_SPEED_MMS * REFRESH_RATE, axis='Y')
        time.sleep(REFRESH_RATE)
    
    #Mueve la pizza en cinta circular
    while (not (is_at_station(part.Pose(), STATION_6_PRE_PERSON_LAST_Y, axis='Y') and is_at_station(part.Pose(), STATION_6_PRE_PERSON_X, axis='X'))):
        if not is_at_station(part.Pose(), STATION_6_PRE_PERSON_LAST_Y, axis='Y'):
            conveyor_move_object(part, 200 * REFRESH_RATE, axis='Y')
        if not is_at_station(part.Pose(), STATION_6_PRE_PERSON_X, axis='X'):
            conveyor_move_object(part, -200 * REFRESH_RATE, axis='X') 
        time.sleep(REFRESH_RATE)

    while not is_at_station(part.Pose(), STATION_6_FIRST_POSITION, axis='X'):
        conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
        time.sleep(REFRESH_RATE)

    while not is_at_station(part.Pose(), STATION_6_SECOND_POSITION, axis='X'):
        #Si no hay pizza delante le da permiso para seguir
        with mutex_espera_2:
            if not espera_2:
                permiso = False
            else:
                permiso = True

        #Si se da el evento borra la pizza y acaba el hilo
        if event and event.is_set():
            RDK.Delete(part)
            del qr_events[usuario]
            return
        
        #Si tiene permiso, avanza
        if permiso:
            conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
            time.sleep(REFRESH_RATE)
        else:
            time.sleep(1)

    while not is_at_station(part.Pose(), STATION_6_THIRD_POSITION, axis='X'):
        #Si no hay pizza delante le da permiso para seguir
        with mutex_espera_3:
            if not espera_3:
                permiso_2 = False
            else: 
                permiso_2 = True
        
        #Si no tiene permiso para avanzar, le dice a la anterior que espere
        if not permiso_2:
            with mutex_espera_2:
                espera_2 = False

        #Si se da el evento borra la pizza y acaba el hilo
        if event and event.is_set():
            RDK.Delete(part)
            del qr_events[usuario]
            with mutex_espera_2:
                espera_2 = True
            return

        #Si tiene permiso, avanza y le dice a la anterior que ya puede avanzar
        if permiso_2:
            with mutex_espera_2:
                espera_2 = True
            conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
            time.sleep(REFRESH_RATE)
        else:
            time.sleep(1)

    while not is_at_station(part.Pose(), STATION_6_LAST_POSITION, axis='X'):
        #Si no hay pizza delante le da permiso para seguir     
        with mutex_espera_4:
            if not espera_4:
                permiso_3 = False
            else:
                permiso_3 = True

        #Si no tiene permiso para avanzar, le dice a la anterior que espere
        if not permiso_3:
            with mutex_espera_3:
                espera_3 = False 

        #Si se da el evento borra la pizza y acaba el hilo
        if event and event.is_set():
            RDK.Delete(part)
            del qr_events[usuario]
            with mutex_espera_3:
                espera_3 = True
            return
        
        #Si tiene permiso, avanza y le dice a la anterior que ya puede avanzar
        if permiso_3:
            with mutex_espera_3:
                espera_3 = True

            conveyor_move_object(part, MOVE_SPEED_MMS * REFRESH_RATE, axis='X')
            time.sleep(REFRESH_RATE)
        else:
            time.sleep(1)
    #Al llegar al final le dice a la anterior que espere
    with mutex_espera_4:
        espera_4 = False

    #Si la pizza no ha sido pedida, espera un rato y desaparece diciéndole a la anterior que puede seguir
    if pedido_usuario == DEFAULT_PEDIDO:
        time.sleep(10)
        RDK.Delete(part)
        with mutex_espera_4:
            espera_4 = True
    # Espera al QR o espera 50 segundos y si se da cualquiera de estar, borra la pizza y le dice a la anterior que puede seguir
    else:
        recibido = event.wait(timeout=50)
        if not recibido:
            event.set()
        RDK.Delete(part)
        del qr_events[usuario]
        with mutex_espera_4:
            espera_4 = True

#Gestión de las llamadas a las estaciones y el flujo del programa
def main(pedido_usuario, usuario, pizza_usada):
    global crear_masa_ctrl

    #Si la pizza ha sido pedida, actualiza el estado y obtiene el identificador del pedido
    if pedido_usuario != DEFAULT_PEDIDO:
        client_tcp.publish(TOPIC_LEDS, "PREPARACION")
        identificador_pedido = actualizar_estado(usuario, "PREPARACION",None)
    else:
        identificador_pedido=None

    #Si la pizza ha sido pedida, obtiene el usuario y el tipo de pizza pedida
    if usuario is not None or pizza_usada is not None:
        pedido_usuario = f"{usuario}:{pizza_usada}"

    masa_inicial = RDK.Item('Masa', ITEM_TYPE_OBJECT)
    masa_creada = crear_masa_ini(masa_inicial, 'Masa')

    if not masa_creada.Valid():
        print("No se encontró la masa inicial.")
    else:
        masa_procesada = run_station_1(masa_creada)
        if masa_procesada:
            masa_procesada = run_station_2(masa_procesada)
        if masa_procesada:
            masa_procesada = run_station_3(masa_procesada, pedido_usuario, identificador_pedido)
        if masa_procesada:
            masa_procesada = run_station_4(masa_procesada)
        if masa_procesada:
            masa_procesada = run_station_5(masa_procesada)
        if masa_procesada:
            run_station_6(masa_procesada, pedido_usuario, identificador_pedido)

#Conectarse al broker de websockets
client = mqtt.Client(transport="websockets")
client.on_connect = on_connect_ws
client.on_message = on_message_ws
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)
client.connect(BROKER_WS, PORT_WS, keepalive=60)
client.loop_start() 

#Conectarse al broker de tcp
client_tcp = mqtt.Client(protocol=mqtt.MQTTv5)
client_tcp.on_message = on_message_tcp
client_tcp.connect(BROKER_TCP, PORT_TCP)
client_tcp.subscribe(TOPIC_QR)
client_tcp.subscribe(TOPIC_SETA)
client_tcp.loop_start()

#Creamos una lista de hilos
threads = []

#Generamos un bucle continuo de la planta de automatización
while True:
    with mutex_siguiente_ronda:
        #Si no tiene permiso para hacer una pizza, duerme
        if siguiente_ronda:
            #Extrae el usuario y la pizza de la cola y si no hay pone las variables predeterminadas para hacer una pizza sin pedido asociado
            try:
                usuario = cola_usuarios.get_nowait()
                pizza   = cola_pizzas.get_nowait()
                pedido  = f"{pizza}:{usuario}"
            except Empty:
                pedido = DEFAULT_PEDIDO
                usuario = None
                pizza   = None
            #Controla que solo se crea una pizza cada vez, cada pizza es un hilo que se añade a la lista y quita el permiso para hacer nuevas pizzas
            with mutex_crear:
                if crear_masa_ctrl:
                    crear_masa_ctrl = False
                    threads.append(threading.Thread(target=main, args=(pedido,usuario,pizza,), daemon=True))
                    threads[-1].start()
                    siguiente_ronda = False
                    time.sleep(0.5)
                else:
                    time.sleep(REFRESH_RATE)
        else:
            time.sleep(REFRESH_RATE)
