# Automatizado_de_pizzeria
Este proyecto incorpora a una celula desarrollada en robodk para la automatización del proceso realizado en una pizzería, las tecnologías necesarias para simular el entorno completo de este negocio.
Mediante una página web diseñada, la cual se refleja en el repositorio de Autopizza_web, los clientes pueden realizar su pedido para ser procesado  por la pizzería.
El script de python de Iniproceso se encarga mediante el uso de hilos y semáforos del control de la celula del robodk además de la gestión de consultas de la base de datos.
La base de datos relacional guarda toda la información requerida del cliente y su pedido y mediante el empleo de triggers logramos la automatizacion de acciones relacionadas con el pedido y con la gestión de la bdd en si.
El script de consulta_bdd_final, se encarga de gestionar la inserción de los datos requeridos en la base de datos.
La célula de robodk simula el proceso de creación de una pizza según la pide el cliente.
Todos los procesos llevan incorporado un sistema de comunicaciones por mqtt para el correcto funcionamiento de la pizzería.
