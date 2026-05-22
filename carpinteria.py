import streamlit as st
import pandas as pd
import datetime
import os

# --- CONFIGURACIÓN DE ARCHIVOS ---
ARCHIVO_INV = "Inventario.xlsx"
ARCHIVO_MEMORIAS = "Memorias.xlsx"
ARCHIVO_USUARIOS = "usuarios_taller.csv"
ARCHIVO_LOG = "auditoria_taller.txt"

# Configuración de la página
st.set_page_config(page_title="Control Taller CIMM", layout="wide")

# Inicializar archivo de usuarios si no existe
if not os.path.exists(ARCHIVO_USUARIOS):
    df_u = pd.DataFrame(
        [['alejandro', 'Alejandro312.', 'ADMIN']],
        columns=['Usuario', 'Password', 'Rol']
    )
    df_u.to_csv(ARCHIVO_USUARIOS, index=False)

# --- LOGIN ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:

    st.title("🔐 Acceso al Sistema de Carpintería")

    user = st.text_input("Usuario")
    pas = st.text_input("Contraseña", type="password")

    if st.button("Entrar"):

        df_u = pd.read_csv(ARCHIVO_USUARIOS)

        user_match = df_u[
            (df_u['Usuario'] == user.lower()) &
            (df_u['Password'] == pas)
        ]

        if not user_match.empty:

            st.session_state.autenticado = True
            st.session_state.username = user
            st.session_state.rol = user_match.iloc[0]['Rol']

            st.rerun()

        else:
            st.error("Usuario o contraseña incorrectos")

else:

    # --- SIDEBAR ---
    st.sidebar.title(
        f"Bienvenido, {st.session_state.username.capitalize()}"
    )

    opcion = st.sidebar.radio(
        "Menú",
        [
            "Inventario",
            "Registrar Movimiento",
            "Guía para Aprendices",
            "Panel Admin"
        ]
    )

    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

    # =========================================================
    # 1. INVENTARIO
    # =========================================================
    if opcion == "Inventario":

        st.header("📊 Saldo de Materiales en Taller")

        try:

            df = pd.read_excel(
                ARCHIVO_INV,
                sheet_name="Resumen"
            )

            busqueda = st.text_input(
                "Buscar material (ej: Marco, 3893, Sillar)"
            )

            if busqueda:

                df = df[
                    df['Descripcion'].astype(str).str.contains(
                        busqueda,
                        case=False,
                        na=False
                    )
                    |
                    df['Referencia'].astype(str).str.contains(
                        busqueda,
                        case=False,
                        na=False
                    )
                ]

            st.dataframe(
                df[['Referencia', 'Descripcion', 'Saldo']],
                use_container_width=True
            )

        except:
            st.error("No se encontró el archivo Inventario.xlsx")

    # =========================================================
    # 2. REGISTRAR MOVIMIENTO
    # =========================================================
    elif opcion == "Registrar Movimiento":

        st.header("📝 Registro de Entradas y Salidas")

        with st.form("registro"):

            tipo = st.selectbox(
                "Tipo de movimiento",
                [
                    "SALIDA (Gasto)",
                    "ENTRADA (Ingreso)"
                ]
            )

            ref = st.text_input("Referencia del material")

            cant = st.text_input(
                "Cantidad (cm o Unidades)"
            )

            obra = st.text_input(
                "Nota / Obra / Destino"
            )

            enviar = st.form_submit_button(
                "Guardar Registro"
            )

            if enviar:

                fecha = datetime.datetime.now().strftime(
                    "%Y-%m-%d %H:%M"
                )

                log = (
                    f"[{fecha}] | "
                    f"{tipo} | "
                    f"{st.session_state.username} | "
                    f"REF: {ref} | "
                    f"CANT: {cant} | "
                    f"NOTA: {obra}\n"
                )

                with open(ARCHIVO_LOG, "a") as f:
                    f.write(log)

                st.success(
                    "¡Registro guardado con éxito!"
                )

    # =========================================================
    # 3. GUÍA PARA APRENDICES
    # =========================================================
    elif opcion == "Guía para Aprendices":

        st.header("📏 Consulta de Perfiles por Proyecto")

        proyecto = st.selectbox(
            "Seleccione el proyecto",
            ["PTA", "DBB", "PB", "DO"]
        )

        try:

            df_m = pd.read_excel(
                ARCHIVO_MEMORIAS,
                sheet_name=proyecto
            )

            st.subheader(
                f"Perfiles necesarios para {proyecto}"
            )

            st.table(
                df_m.iloc[29:35, [10, 12, 14]]
            )

            st.info(
                "Nota: Verifique los descuentos de corte antes de usar la tronzadora."
            )

        except:
            st.error(
                "No se pudo cargar la guía de Memorias.xlsx"
            )

    # =========================================================
    # 4. PANEL ADMIN
    # =========================================================
    elif opcion == "Panel Admin":

        if st.session_state.rol == "ADMIN":

            st.header("⚙️ Control de Administrador")

            tab1, tab2, tab3 = st.tabs(
                [
                    "Auditoría",
                    "Crear Usuarios",
                    "Restablecer Contraseña"
                ]
            )

            # -----------------------------------
            # TAB 1 - AUDITORÍA
            # -----------------------------------
            with tab1:

                if os.path.exists(ARCHIVO_LOG):

                    with open(ARCHIVO_LOG, "r") as f:

                        st.text_area(
                            "Historial de movimientos",
                            f.read(),
                            height=300
                        )

                else:
                    st.write("No hay registros aún.")

            # -----------------------------------
            # TAB 2 - CREAR USUARIOS
            # -----------------------------------
            with tab2:

                new_u = st.text_input(
                    "Nombre del compañero"
                )

                new_p = st.text_input(
                    "Contraseña para él",
                    type="password"
                )

                new_r = st.selectbox(
                    "Rol",
                    ["USER", "ADMIN"]
                )

                if st.button("Crear Usuario"):

                    if new_u and new_p:

                        df_nuevo = pd.DataFrame(
                            [[
                                new_u.lower(),
                                new_p,
                                new_r
                            ]],
                            columns=[
                                'Usuario',
                                'Password',
                                'Rol'
                            ]
                        )

                        df_nuevo.to_csv(
                            ARCHIVO_USUARIOS,
                            mode='a',
                            header=False,
                            index=False
                        )

                        st.success(
                            f"Usuario {new_u} creado."
                        )

                    else:
                        st.warning(
                            "Complete todos los campos."
                        )

            # -----------------------------------
            # TAB 3 - RESTABLECER CONTRASEÑA
            # -----------------------------------
            with tab3:

                st.subheader(
                    "🔑 Restablecer Contraseña"
                )

                usuario_reset = st.text_input(
                    "Usuario a restablecer"
                )

                nueva_pass = st.text_input(
                    "Nueva contraseña",
                    type="password"
                )

                if st.button(
                    "Restablecer Contraseña"
                ):

                    df_users = pd.read_csv(
                        ARCHIVO_USUARIOS
                    )

                    if usuario_reset.lower() in df_users['Usuario'].values:

                        df_users.loc[
                            df_users['Usuario'] == usuario_reset.lower(),
                            'Password'
                        ] = nueva_pass

                        df_users.to_csv(
                            ARCHIVO_USUARIOS,
                            index=False
                        )

                        st.success(
                            f"Contraseña actualizada para {usuario_reset}"
                        )

                    else:
                        st.error(
                            "Usuario no encontrado"
                        )

        else:

            st.warning(
                "No tienes permiso para ver esta sección."
            )