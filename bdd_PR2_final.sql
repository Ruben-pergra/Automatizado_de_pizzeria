PGDMP      (                }        	   Autopicha    17.5    17.5 5    ~           0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                           false                       0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                           false            �           0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                           false            �           1262    16927 	   Autopicha    DATABASE     ~   CREATE DATABASE "Autopicha" WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'Spanish_Spain.1252';
    DROP DATABASE "Autopicha";
                     postgres    false                        3079    16928 	   uuid-ossp 	   EXTENSION     ?   CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA public;
    DROP EXTENSION "uuid-ossp";
                        false            �           0    0    EXTENSION "uuid-ossp"    COMMENT     W   COMMENT ON EXTENSION "uuid-ossp" IS 'generate universally unique identifiers (UUIDs)';
                             false    2            �            1255    16939    actualizar_updated_at_topics()    FUNCTION     6  CREATE FUNCTION public.actualizar_updated_at_topics() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Actualiza el updated_at del topic referenciado por la fila recién insertada
  UPDATE public.topics
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id_serial = NEW.topic_id;
  RETURN NEW;
END;
$$;
 5   DROP FUNCTION public.actualizar_updated_at_topics();
       public               postgres    false            �            1255    16940    ajusta_ingrediente_por_pedido()    FUNCTION     �  CREATE FUNCTION public.ajusta_ingrediente_por_pedido() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  ing_desc     text;
  updated_count int;
BEGIN
  -- Averiguamos el nombre del ingrediente que toca según el nombre de la pizza
  SELECT ingrediente_descripcion
    INTO ing_desc
  FROM public.receta_pizza
  WHERE nombre_pizza = NEW.pizza;    -- <-- ahora usa NEW.pizza

  IF NOT FOUND THEN
    RAISE NOTICE '[detalle_pedido→ingrediente] Sin receta para "%"', NEW.pizza;
    RETURN NEW;
  END IF;
  RAISE NOTICE '[detalle_pedido→ingrediente] Ingrediente a usar: %', ing_desc;

  -- Actualizamos ese ingrediente en la tabla ingredientes
  UPDATE public.ingredientes AS i
     SET cantidad_disponible = i.cantidad_disponible - 1,
         pizza               = NEW.id_pedido  -- asignamos la orden
    WHERE i.descripcion = ing_desc
  RETURNING 1
    INTO updated_count;

  IF updated_count = 0 THEN
    RAISE NOTICE '[detalle_pedido→ingrediente] ¡No se encontró "%" en ingredientes!', ing_desc;
  ELSE
    RAISE NOTICE '[detalle_pedido→ingrediente] Stock actualizado y pizza asignada (% fila)', updated_count;
  END IF;

  RETURN NEW;
END;
$$;
 6   DROP FUNCTION public.ajusta_ingrediente_por_pedido();
       public               postgres    false            �            1255    16941 ,   descuenta_ingredientes_por_pizza_terminada()    FUNCTION     �  CREATE FUNCTION public.descuenta_ingredientes_por_pizza_terminada() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Por cada ingrediente de la receta de la pizza que acabamos de fabricar:
  UPDATE public.ingredientes AS i
     SET cantidad_disponible = i.cantidad_disponible - rp.cantidad
    FROM public.receta_pizza AS rp
   WHERE rp.nombre_pizza = NEW.descripcion
     AND i.identificador = rp.ingrediente_id;

  RETURN NEW;
END;
$$;
 C   DROP FUNCTION public.descuenta_ingredientes_por_pizza_terminada();
       public               postgres    false            �            1255    24800    fn_contador_tipo_pizza()    FUNCTION     +  CREATE FUNCTION public.fn_contador_tipo_pizza() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  total integer;
BEGIN
  SELECT COUNT(*) INTO total
    FROM public.pizza_terminada
   WHERE descripcion = NEW.descripcion;

  NEW.cantidad_tipo_pizzas_hechas := total + 1;
  RETURN NEW;
END;
$$;
 /   DROP FUNCTION public.fn_contador_tipo_pizza();
       public               postgres    false            �            1255    16942 #   fn_ingrediente_to_pizza_terminada()    FUNCTION     [  CREATE FUNCTION public.fn_ingrediente_to_pizza_terminada() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  pizza_name public.detalle_pedido.pizza%TYPE;
  ing_desc   public.receta_pizza.ingrediente_descripcion%TYPE;
BEGIN
  -- 1) Obtener el nombre de la pizza desde detalle_pedido
  SELECT dp.pizza
    INTO pizza_name
    FROM public.detalle_pedido dp
   WHERE dp.id_pedido = NEW.pizza
   LIMIT 1;

  IF pizza_name IS NULL THEN
    RAISE EXCEPTION 'Pedido % no existe en detalle_pedido.', NEW.pizza;
  END IF;

  -- 2) Obtener un ingrediente de la receta para esa pizza
  SELECT ingrediente_descripcion
    INTO ing_desc
    FROM public.receta_pizza
   WHERE nombre_pizza = pizza_name
   LIMIT 1;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'No existe receta para pizza "%".', pizza_name;
  END IF;

  -- 3) Insertar en pizza_terminada con estado 'pendiente'
  INSERT INTO public.pizza_terminada (
    descripcion,
    fecha_fabricacion,
    estado,
    ingrediente_utilizado,
    pedido
  ) VALUES (
    pizza_name,
    CURRENT_DATE,
    'pendiente',
    ing_desc,
    NEW.pizza
  );

  RETURN NEW;
END;
$$;
 :   DROP FUNCTION public.fn_ingrediente_to_pizza_terminada();
       public               postgres    false            �            1255    16943 !   refresh_updated_at_ingredientes()    FUNCTION     �   CREATE FUNCTION public.refresh_updated_at_ingredientes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Solo cambian columnas distintas de updated_at, no queremos bucles infinitos
  NEW.updated_at := CURRENT_TIMESTAMP;
  RETURN NEW;
END;
$$;
 8   DROP FUNCTION public.refresh_updated_at_ingredientes();
       public               postgres    false            �            1259    16944    cliente    TABLE     �   CREATE TABLE public.cliente (
    id_cliente uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    usuario character varying(100) NOT NULL,
    contrasenya character varying(100) NOT NULL,
    topic_id uuid NOT NULL
);
    DROP TABLE public.cliente;
       public         heap r       postgres    false    2            �            1259    16948    datos_nevera    TABLE     �   CREATE TABLE public.datos_nevera (
    id_serial uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    valor_numeric real NOT NULL,
    fecha_dato timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    topic_id uuid NOT NULL
);
     DROP TABLE public.datos_nevera;
       public         heap r       postgres    false    2            �            1259    17600    detalle_pedido    TABLE       CREATE TABLE public.detalle_pedido (
    id_detalle_pedido uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    id_pedido uuid NOT NULL,
    id_cliente uuid NOT NULL,
    pizza character varying(100) NOT NULL,
    usuario character varying(100) NOT NULL
);
 "   DROP TABLE public.detalle_pedido;
       public         heap r       postgres    false    2            �            1259    16953    ingredientes    TABLE       CREATE TABLE public.ingredientes (
    identificador uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    descripcion character varying(255),
    cantidad_disponible integer NOT NULL,
    pizza uuid,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
     DROP TABLE public.ingredientes;
       public         heap r       postgres    false    2            �            1259    16958    pedido    TABLE     �   CREATE TABLE public.pedido (
    id_pedido uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    fecha timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    estado character varying(50) NOT NULL,
    cliente uuid NOT NULL
);
    DROP TABLE public.pedido;
       public         heap r       postgres    false    2            �            1259    16964    pizza_terminada    TABLE     �  CREATE TABLE public.pizza_terminada (
    identificador uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    descripcion character varying(255),
    cantidad_tipo_pizzas_hechas integer DEFAULT 0 NOT NULL,
    fecha_fabricacion date DEFAULT CURRENT_DATE NOT NULL,
    estado character varying(50) NOT NULL,
    ingrediente_utilizado character varying(255) NOT NULL,
    pedido uuid NOT NULL
);
 #   DROP TABLE public.pizza_terminada;
       public         heap r       postgres    false    2            �            1259    16973    receta_pizza    TABLE     �   CREATE TABLE public.receta_pizza (
    nombre_pizza character varying(100) NOT NULL,
    ingrediente_descripcion character varying(255) NOT NULL,
    id_ingrediente uuid
);
     DROP TABLE public.receta_pizza;
       public         heap r       postgres    false            �            1259    16976    topics    TABLE       CREATE TABLE public.topics (
    id_serial uuid DEFAULT public.uuid_generate_v4() NOT NULL,
    nombre_text character varying(255),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
    DROP TABLE public.topics;
       public         heap r       postgres    false    2            t          0    16944    cliente 
   TABLE DATA           M   COPY public.cliente (id_cliente, usuario, contrasenya, topic_id) FROM stdin;
    public               postgres    false    218   �S       u          0    16948    datos_nevera 
   TABLE DATA           V   COPY public.datos_nevera (id_serial, valor_numeric, fecha_dato, topic_id) FROM stdin;
    public               postgres    false    219   �T       {          0    17600    detalle_pedido 
   TABLE DATA           b   COPY public.detalle_pedido (id_detalle_pedido, id_pedido, id_cliente, pizza, usuario) FROM stdin;
    public               postgres    false    225   �T       v          0    16953    ingredientes 
   TABLE DATA           j   COPY public.ingredientes (identificador, descripcion, cantidad_disponible, pizza, updated_at) FROM stdin;
    public               postgres    false    220   VV       w          0    16958    pedido 
   TABLE DATA           C   COPY public.pedido (id_pedido, fecha, estado, cliente) FROM stdin;
    public               postgres    false    221   sW       x          0    16964    pizza_terminada 
   TABLE DATA           �   COPY public.pizza_terminada (identificador, descripcion, cantidad_tipo_pizzas_hechas, fecha_fabricacion, estado, ingrediente_utilizado, pedido) FROM stdin;
    public               postgres    false    222   �X       y          0    16973    receta_pizza 
   TABLE DATA           ]   COPY public.receta_pizza (nombre_pizza, ingrediente_descripcion, id_ingrediente) FROM stdin;
    public               postgres    false    223   �X       z          0    16976    topics 
   TABLE DATA           P   COPY public.topics (id_serial, nombre_text, created_at, updated_at) FROM stdin;
    public               postgres    false    224   oY       �           2606    16983    cliente cliente_pkey 
   CONSTRAINT     Z   ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_pkey PRIMARY KEY (id_cliente);
 >   ALTER TABLE ONLY public.cliente DROP CONSTRAINT cliente_pkey;
       public                 postgres    false    218            �           2606    16985    datos_nevera datos_nevera_pkey 
   CONSTRAINT     c   ALTER TABLE ONLY public.datos_nevera
    ADD CONSTRAINT datos_nevera_pkey PRIMARY KEY (id_serial);
 H   ALTER TABLE ONLY public.datos_nevera DROP CONSTRAINT datos_nevera_pkey;
       public                 postgres    false    219            �           2606    17605 "   detalle_pedido detalle_pedido_pkey 
   CONSTRAINT     o   ALTER TABLE ONLY public.detalle_pedido
    ADD CONSTRAINT detalle_pedido_pkey PRIMARY KEY (id_detalle_pedido);
 L   ALTER TABLE ONLY public.detalle_pedido DROP CONSTRAINT detalle_pedido_pkey;
       public                 postgres    false    225            �           2606    16987    ingredientes ingredientes_pkey 
   CONSTRAINT     g   ALTER TABLE ONLY public.ingredientes
    ADD CONSTRAINT ingredientes_pkey PRIMARY KEY (identificador);
 H   ALTER TABLE ONLY public.ingredientes DROP CONSTRAINT ingredientes_pkey;
       public                 postgres    false    220            �           2606    16989    pedido pedido_pkey 
   CONSTRAINT     W   ALTER TABLE ONLY public.pedido
    ADD CONSTRAINT pedido_pkey PRIMARY KEY (id_pedido);
 <   ALTER TABLE ONLY public.pedido DROP CONSTRAINT pedido_pkey;
       public                 postgres    false    221            �           2606    16991 $   pizza_terminada pizza_terminada_pkey 
   CONSTRAINT     m   ALTER TABLE ONLY public.pizza_terminada
    ADD CONSTRAINT pizza_terminada_pkey PRIMARY KEY (identificador);
 N   ALTER TABLE ONLY public.pizza_terminada DROP CONSTRAINT pizza_terminada_pkey;
       public                 postgres    false    222            �           2606    16993    receta_pizza receta_pizza_pkey 
   CONSTRAINT     f   ALTER TABLE ONLY public.receta_pizza
    ADD CONSTRAINT receta_pizza_pkey PRIMARY KEY (nombre_pizza);
 H   ALTER TABLE ONLY public.receta_pizza DROP CONSTRAINT receta_pizza_pkey;
       public                 postgres    false    223            �           2606    16995    topics topics_nombre_text_key 
   CONSTRAINT     _   ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_nombre_text_key UNIQUE (nombre_text);
 G   ALTER TABLE ONLY public.topics DROP CONSTRAINT topics_nombre_text_key;
       public                 postgres    false    224            �           2606    16997    topics topics_pkey 
   CONSTRAINT     W   ALTER TABLE ONLY public.topics
    ADD CONSTRAINT topics_pkey PRIMARY KEY (id_serial);
 <   ALTER TABLE ONLY public.topics DROP CONSTRAINT topics_pkey;
       public                 postgres    false    224            �           2606    16999 )   ingredientes unq_ingredientes_descripcion 
   CONSTRAINT     k   ALTER TABLE ONLY public.ingredientes
    ADD CONSTRAINT unq_ingredientes_descripcion UNIQUE (descripcion);
 S   ALTER TABLE ONLY public.ingredientes DROP CONSTRAINT unq_ingredientes_descripcion;
       public                 postgres    false    220            �           2620    17616 4   detalle_pedido trg_ajusta_ingrediente_detalle_pedido    TRIGGER     �   CREATE TRIGGER trg_ajusta_ingrediente_detalle_pedido AFTER INSERT OR UPDATE ON public.detalle_pedido FOR EACH ROW EXECUTE FUNCTION public.ajusta_ingrediente_por_pedido();
 M   DROP TRIGGER trg_ajusta_ingrediente_detalle_pedido ON public.detalle_pedido;
       public               postgres    false    225    251            �           2620    24803 '   pizza_terminada trg_contador_tipo_pizza    TRIGGER     �   CREATE TRIGGER trg_contador_tipo_pizza BEFORE INSERT ON public.pizza_terminada FOR EACH ROW EXECUTE FUNCTION public.fn_contador_tipo_pizza();
 @   DROP TRIGGER trg_contador_tipo_pizza ON public.pizza_terminada;
       public               postgres    false    222    239            �           2620    17001 *   cliente trg_datos_nevera_actualizar_topics    TRIGGER     �   CREATE TRIGGER trg_datos_nevera_actualizar_topics AFTER INSERT ON public.cliente FOR EACH ROW EXECUTE FUNCTION public.actualizar_updated_at_topics();
 C   DROP TRIGGER trg_datos_nevera_actualizar_topics ON public.cliente;
       public               postgres    false    236    218            �           2620    17002 /   datos_nevera trg_datos_nevera_actualizar_topics    TRIGGER     �   CREATE TRIGGER trg_datos_nevera_actualizar_topics AFTER INSERT ON public.datos_nevera FOR EACH ROW EXECUTE FUNCTION public.actualizar_updated_at_topics();
 H   DROP TRIGGER trg_datos_nevera_actualizar_topics ON public.datos_nevera;
       public               postgres    false    219    236            �           2620    24802 /   ingredientes trg_ingrediente_to_pizza_terminada    TRIGGER     �   CREATE TRIGGER trg_ingrediente_to_pizza_terminada AFTER UPDATE OF pizza ON public.ingredientes FOR EACH ROW WHEN ((new.pizza IS NOT NULL)) EXECUTE FUNCTION public.fn_ingrediente_to_pizza_terminada();
 H   DROP TRIGGER trg_ingrediente_to_pizza_terminada ON public.ingredientes;
       public               postgres    false    220    220    252    220            �           2620    17004 #   ingredientes trg_refresh_updated_at    TRIGGER     �   CREATE TRIGGER trg_refresh_updated_at BEFORE UPDATE ON public.ingredientes FOR EACH ROW EXECUTE FUNCTION public.refresh_updated_at_ingredientes();
 <   DROP TRIGGER trg_refresh_updated_at ON public.ingredientes;
       public               postgres    false    238    220            �           2606    17005    cliente cliente_topic_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES public.topics(id_serial);
 G   ALTER TABLE ONLY public.cliente DROP CONSTRAINT cliente_topic_id_fkey;
       public               postgres    false    224    218    4817            �           2606    17010 '   datos_nevera datos_nevera_topic_id_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.datos_nevera
    ADD CONSTRAINT datos_nevera_topic_id_fkey FOREIGN KEY (topic_id) REFERENCES public.topics(id_serial);
 Q   ALTER TABLE ONLY public.datos_nevera DROP CONSTRAINT datos_nevera_topic_id_fkey;
       public               postgres    false    224    4817    219            �           2606    17606 *   detalle_pedido detalle_pedido_cliente_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.detalle_pedido
    ADD CONSTRAINT detalle_pedido_cliente_fkey FOREIGN KEY (id_cliente) REFERENCES public.cliente(id_cliente);
 T   ALTER TABLE ONLY public.detalle_pedido DROP CONSTRAINT detalle_pedido_cliente_fkey;
       public               postgres    false    225    4801    218            �           2606    17611 )   detalle_pedido detalle_pedido_pedido_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.detalle_pedido
    ADD CONSTRAINT detalle_pedido_pedido_fkey FOREIGN KEY (id_pedido) REFERENCES public.pedido(id_pedido) ON DELETE CASCADE;
 S   ALTER TABLE ONLY public.detalle_pedido DROP CONSTRAINT detalle_pedido_pedido_fkey;
       public               postgres    false    225    221    4809            �           2606    17015 %   ingredientes ingredientes_pedido_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.ingredientes
    ADD CONSTRAINT ingredientes_pedido_fkey FOREIGN KEY (pizza) REFERENCES public.pedido(id_pedido) ON UPDATE CASCADE ON DELETE RESTRICT;
 O   ALTER TABLE ONLY public.ingredientes DROP CONSTRAINT ingredientes_pedido_fkey;
       public               postgres    false    221    4809    220            �           2606    17020    pedido pedido_cliente_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.pedido
    ADD CONSTRAINT pedido_cliente_fkey FOREIGN KEY (cliente) REFERENCES public.cliente(id_cliente);
 D   ALTER TABLE ONLY public.pedido DROP CONSTRAINT pedido_cliente_fkey;
       public               postgres    false    4801    221    218            �           2606    17025 :   pizza_terminada pizza_terminada_ingrediente_utilizado_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.pizza_terminada
    ADD CONSTRAINT pizza_terminada_ingrediente_utilizado_fkey FOREIGN KEY (ingrediente_utilizado) REFERENCES public.ingredientes(descripcion);
 d   ALTER TABLE ONLY public.pizza_terminada DROP CONSTRAINT pizza_terminada_ingrediente_utilizado_fkey;
       public               postgres    false    222    4807    220            �           2606    17030 +   pizza_terminada pizza_terminada_pedido_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.pizza_terminada
    ADD CONSTRAINT pizza_terminada_pedido_fkey FOREIGN KEY (pedido) REFERENCES public.pedido(id_pedido);
 U   ALTER TABLE ONLY public.pizza_terminada DROP CONSTRAINT pizza_terminada_pedido_fkey;
       public               postgres    false    222    4809    221            �           2606    17035 ,   receta_pizza receta_pizza_materia_prima_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.receta_pizza
    ADD CONSTRAINT receta_pizza_materia_prima_fkey FOREIGN KEY (id_ingrediente) REFERENCES public.ingredientes(identificador) ON UPDATE CASCADE ON DELETE RESTRICT;
 V   ALTER TABLE ONLY public.receta_pizza DROP CONSTRAINT receta_pizza_materia_prima_fkey;
       public               postgres    false    223    220    4805            t   �   x���AN1��u�.Fqb'��Ē5�N`T�2ROO������x�L�f�@Q#4,J.�Q\j����g�����z�k���e�2z��:�hT�):*i������@�1athMH��SG��ᴝo���G ���-�ӈ@�H��z+���5�l�}\��ws.
�S*5�Nɐ1ǖэ������?"�=-���\m�      u      x������ � �      {   e  x�5��j]1E�>��`��C��BG��B�%�=$�n�|}h&������(�jaYՁt,����J�xPZ�Tj�mo��D��e9v��S�6���j�X�\��^���#[�?����ǩr�k���|����4��Z� ;����$�]��`l' ���qb�9���P�t�;Ǩd�$}��Ňy��x]~I߮����G�:C������>�#r��4K�:i7��w�иB?����3&ʳt�
F�!,$��*Zܵ(�&��_ov��/~;����l�x|,�5Sd!�=S�d,���yy|.�F^;���^--��6���G-�2����O���i��������b�ϻ�8�K�+      v     x�}��mcQ��si���RK6�%��=���i/E�J�{��8��h�X]h�LWЬ��%�T:�����A�xPۉ��f��Xo��|���΃�;`��7�o}�Nj����T�P�dـ%>�]�rX_G|؟�������W�(�8aV
�1��4yM_3�����;�U�v�O!�2���������۹�8k�������ݧJF�g^����P�v���*p�R����{~ݮ��E�Z���
K�B�C̓7n��3���r����s!      w     x�e�;nD1�z�*���ϘYKl��&J��+.G��B�`�2��ҶC,w�E="��A���G�'���A,��������zh��+
��8���c�й�S�a-/��+W��� _D��E��5�9�{���h!'�ء�v����!�)�(��K���I�mw?#ͳ�N�E�ѻ�v�M����!�HM����dz_�5.dISX��|:P(+�>Ǵ�[�������&��͕Z9t��tc�=��D�9c.�>��� �o�      x      x������ � �      y   �   x�5�1n�0@�Y�ɢdq��)�� )
�P�q�Ys��F������x��+-�]�v.q�H(@, g! �p"�����?�������n����ݜ�D�m�n6V.PQ
���&�\��yQ��p�:Vg�z����S �1B�Kg����.��Ͷ���F�R�%�cT3�>h��J�����{�r4G�      z   r   x�]�1�  �9��08��+�J��H�Q��=��aY��-4�0W�$C^'*����5������Os�W�}�9�(����
/�H6���
y�,��4� ���VJ�b�!     