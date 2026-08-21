import datetime
import json
import os
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Taller CIMM", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_gsheets():
    if "gcp_service_account" in st.secrets:
        secrets_gcp = st.secrets["gcp_service_account"]
        service_account_info = {
            "type": secrets_gcp["type"],
            "project_id": secrets_gcp["project_id"],
            "private_key_id": secrets_gcp["private_key_id"],
            "private_key": secrets_gcp["private_key"].replace('\\n', '\n'),
            "client_email": secrets_gcp["client_email"],
            "client_id": secrets_gcp["client_id"],
            "auth_uri": secrets_gcp["auth_uri"],
            "token_uri": secrets_gcp["token_uri"],
            "auth_provider_x509_cert_url": secrets_gcp["auth_provider_x509_cert_url"],
            "client_x509_cert_url": secrets_gcp["client_x509_cert_url"],
            "universe_domain": secrets_gcp["universe_domain"]
        }
        creds = Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
    elif "GCP_SERVICE_ACCOUNT" in os.environ:
        service_account_info = json.loads(os.environ["GCP_SERVICE_ACCOUNT"])
        creds = Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
    else:
        archivo_local = "credentials.json"
        if os.path.exists(archivo_local):
            creds = Credentials.from_service_account_file(archivo_local, scopes=SCOPES)
        else:
            return None
    client = gspread.authorize(creds)
    return client

# --- FUNCIONES AUXILIARES DE LECTURA Y ESCRITURA EN SHEETS ---
def obtener_hoja(nombre_hoja):
    cliente = conectar_gsheets()
    if cliente:
        try:
            return cliente.open("general").worksheet(nombre_hoja)
        except Exception:
            doc = cliente.open("general")
            return doc.add_worksheet(title=nombre_hoja, rows="100", cols="20")
    return None

def cargar_df_hoja(nombre_hoja, columnas_defecto):
    ws = obtener_hoja(nombre_hoja)
    if ws:
        data = ws.get_all_records()
        if data:
            return pd.DataFrame(data)
    return pd.DataFrame(columns=columnas_defecto)

def guardar_df_hoja(nombre_hoja, df):
    ws = obtener_hoja(nombre_hoja)
    if ws:
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.astype(str).values.tolist())

# --- LOGIN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

if not st.session_state.autenticado:
    st.title("🔐 Acceso al Sistema de Carpintería")

    user = st.text_input("Usuario")
    pas = st.text_input("Contraseña", type="password")

    col1, col2 = st.columns([1, 2])

    with col1:
        boton_entrar = st.button("Entrar")

    # --- PANTALLA DE SOLICITUD DE RECUPERACIÓN ---
    st.markdown("---")
    with st.expander("🚨 ¿Olvidaste tu contraseña? Solicita acceso aquí"):
        st.write("Ingresa tus datos. El administrador revisará y aprobará tu cambio en el panel.")

        user_solicita = st.text_input("Tu usuario:", key="user_sol")
        nueva_pass_solicita = st.text_input(
            "Nueva contraseña que deseas:", type="password", key="pass_sol"
        )

        if st.button("Enviar solicitud al Administrador"):
            if user_solicita and nueva_pass_solicita:
                df_u = cargar_df_hoja("Usuarios", ["Usuario", "Password", "Rol"])
                if user_solicita.lower() in df_u["Usuario"].astype(str).str.lower().values:
                    fecha_sol = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                    ws_sol = obtener_hoja("Solicitudes")
                    ws_sol.append_row([fecha_sol, user_solicita.lower(), nueva_pass_solicita])
                    st.success("¡Solicitud enviada! Dile al administrador que te la apruebe en el panel.")
                else:
                    st.error("El usuario ingresado no existe en el sistema.")
            else:
                st.warning("Por favor rellena ambos campos.")

    if boton_entrar:
        df_u = cargar_df_hoja("Usuarios", ["Usuario", "Password", "Rol"])
        if df_u.empty:
            df_u = pd.DataFrame([["alejandro", "Alejandro312.", "ADMIN"]], columns=["Usuario", "Password", "Rol"])
            guardar_df_hoja("Usuarios", df_u)

        user_match = df_u[
            (df_u["Usuario"].astype(str).str.lower() == user.lower()) & 
            (df_u["Password"].astype(str) == pas)
        ]

        if not user_match.empty:
            st.session_state.autenticado = True
            st.session_state.username = user
            st.session_state.rol = user_match.iloc[0]["Rol"]
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

else:
    # --- SIDEBAR ---
    st.sidebar.title(f"Bienvenido, {st.session_state.username.capitalize()}")

    opcion = st.sidebar.radio(
        "Menú",
        ["Inventario", "Registrar Movimiento", "Guía para Aprendices", "Panel Admin"],
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
            ws_gen = obtener_hoja("sheet1") or obtener_hoja("Inventario")
            if ws_gen:
                data = ws_gen.get_all_records()
                df = pd.DataFrame(data)
                busqueda = st.text_input("Buscar material (ej: Marco, 3893, Sillar, Chapa)")

                if busqueda and not df.empty:
                    df = df[
                        df["Descripcion"].astype(str).str.contains(busqueda, case=False, na=False)
                        | df["Referencia"].astype(str).str.contains(busqueda, case=False, na=False)
                    ]

                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No hay registros en la hoja de cálculo.")
            else:
                st.error("No se pudieron cargar las credenciales de Google Sheets.")
        except Exception as e:
            st.error(f"Error al conectar con la hoja de Google Sheets: {e}")

    # =========================================================
    # 2. REGISTRAR MOVIMIENTO
    # =========================================================
    elif opcion == "Registrar Movimiento":
        st.header("📝 Registro de Entradas y Salidas")
        
        try:
            cliente = conectar_gsheets()
            if cliente:
                sheet = cliente.open("general").sheet1
                data = sheet.get_all_records()
                df_inv = pd.DataFrame(data)
                
                opciones_materiales = []
                for idx, row in df_inv.iterrows():
                    ref_str = str(row.get("Referencia", "")).strip()
                    desc_str = str(row.get("Descripcion", "")).strip()
                    if ref_str and ref_str != "nan":
                        label = f"{ref_str} | {desc_str}"
                    else:
                        label = f"{desc_str}"
                    opciones_materiales.append(label)

                with st.form("registro"):
                    tipo = st.selectbox("Tipo de movimiento", ["SALIDA (Gasto)", "ENTRADA (Ingreso)"])
                    material_seleccionado = st.selectbox(
                        "Seleccionar Material", 
                        opciones_materiales,
                        help="Busca por nombre o por referencia"
                    )
                    cant_num = st.number_input("Cantidad", min_value=1, value=1, step=1)
                    obra = st.text_input("Nota / Obra / Destino")

                    enviar = st.form_submit_button("Guardar Registro y Actualizar Inventario")
                    
                    if enviar:
                        fila_index = opciones_materiales.index(material_seleccionado) + 2
                        col_saldo = 12
                        col_target = 11 if "SALIDA" in tipo else 10

                        # 1. Actualizar Entradas/Salidas en Sheet1
                        val_mov_actual = sheet.cell(fila_index, col_target).value
                        try:
                            val_mov_num = int(val_mov_actual) if val_mov_actual else 0
                        except ValueError:
                            val_mov_num = 0
                        sheet.update_cell(fila_index, col_target, val_mov_num + int(cant_num))
                        
                        # 2. Actualizar Saldo (Columna L)
                        val_saldo_actual = sheet.cell(fila_index, col_saldo).value
                        try:
                            saldo_num = int(val_saldo_actual) if val_saldo_actual else 0
                        except ValueError:
                            saldo_num = 0

                        nuevo_saldo = max(0, saldo_num - int(cant_num)) if "SALIDA" in tipo else saldo_num + int(cant_num)
                        sheet.update_cell(fila_index, col_saldo, nuevo_saldo)
                        
                        # 3. Guardar en Auditoría en Google Sheets
                        ws_auditoria = obtener_hoja("Auditoria")
                        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                        ws_auditoria.append_row([fecha, tipo, st.session_state.username, material_seleccionado, cant_num, obra])
                            
                        st.success(f"¡Inventario actualizado! Nuevo saldo de '{material_seleccionado}': {nuevo_saldo} unidades.")
            else:
                st.error("No se pudo conectar a Google Sheets para actualizar el inventario.")
        except Exception as e:
            st.error(f"Error al procesar el movimiento: {e}")

    # =========================================================
    # 3. GUÍA PARA APRENDICES
    # =========================================================
    elif opcion == "Guía para Aprendices":
        st.header("📏 Consulta de Perfiles por Proyecto")
        proyecto = st.selectbox("Seleccione el proyecto", ["PTA", "DBB", "PB", "DO"])
        try:
            ARCHIVO_MEMORIAS = "Memorias.xlsx"
            df_m = pd.read_excel(ARCHIVO_MEMORIAS, sheet_name=proyecto)
            st.subheader(f"Perfiles necesarios para {proyecto}")
            st.table(df_m.iloc[29:35, [10, 12, 14]])
            st.info("Nota: Verifique los descuentos de corte antes de usar la tronzadora.")
        except Exception:
            st.error("No se pudo cargar la guía de Memorias.xlsx")

    # =========================================================
    # 4. PANEL ADMIN
    # =========================================================
    elif opcion == "Panel Admin":
        if st.session_state.rol == "ADMIN":
            st.header("⚙️ Control de Administrador")
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "Auditoría", "📩 Solicitudes de Clave", "Crear Usuarios", "Gestionar/Eliminar Usuarios", "Restablecer Clave"
            ])

            # Tab 1: Auditoría (Con ressaltado en colores)
            with tab1:
                df_aud = cargar_df_hoja("Auditoria", ["Fecha", "Tipo", "Usuario", "Material", "Cantidad", "Nota"])
                if not df_aud.empty:
                    def color_movimiento(val):
                        if "SALIDA" in str(val):
                            return "color: #FF2B2B; font-weight: bold;"
                        elif "ENTRADA" in str(val):
                            return "color: #00D26A; font-weight: bold;"
                        return ""

                    df_estilizado = df_aud.style.map(color_movimiento, subset=["Tipo"])
                    st.dataframe(df_estilizado, use_container_width=True)
                else:
                    st.info("No hay registros en la auditoría aún.")

            # Tab 2: Solicitudes
            with tab2:
                st.subheader("📩 Peticiones de cambio pendientes")
                df_sol = cargar_df_hoja("Solicitudes", ["Fecha", "Usuario", "Nueva_Clave"])
                
                if not df_sol.empty:
                    for i, row in df_sol.iterrows():
                        col_info, col_btn_si, col_btn_no = st.columns([3, 1, 1])
                        with col_info:
                            st.write(f"📅 **{row['Fecha']}** | El usuario **{row['Usuario']}** solicita cambiar clave a: `{row['Nueva_Clave']}`")
                        with col_btn_si:
                            if st.button("✅ Aprobar", key=f"apr_{i}"):
                                df_users = cargar_df_hoja("Usuarios", ["Usuario", "Password", "Rol"])
                                df_users.loc[df_users["Usuario"].astype(str).str.lower() == str(row["Usuario"]).lower(), "Password"] = str(row["Nueva_Clave"])
                                guardar_df_hoja("Usuarios", df_users)
                                
                                df_sol = df_sol.drop(i)
                                guardar_df_hoja("Solicitudes", df_sol)
                                st.success(f"¡Cambio aplicado a {row['Usuario']}!")
                                st.rerun()
                        with col_btn_no:
                            if st.button("❌ Rechazar", key=f"rec_{i}"):
                                df_sol = df_sol.drop(i)
                                guardar_df_hoja("Solicitudes", df_sol)
                                st.warning("Solicitud descartada.")
                                st.rerun()
                        st.markdown("---")
                else:
                    st.info("No tienes solicitudes de cambio de contraseña pendientes. 👍")

            # Tab 3: Crear Usuarios
            with tab3:
                st.subheader("➕ Crear Nuevo Usuario")
                new_u = st.text_input("Nombre del compañero")
                new_p = st.text_input("Contraseña para él", type="password")
                new_r = st.selectbox("Rol", ["USER", "ADMIN"])
                if st.button("Crear Usuario"):
                    if new_u and new_p:
                        df_users = cargar_df_hoja("Usuarios", ["Usuario", "Password", "Rol"])
                        if new_u.lower() in df_users["Usuario"].astype(str).str.lower().values:
                            st.error("El usuario ya existe.")
                        else:
                            df_nuevo = pd.DataFrame([[new_u.lower(), new_p, new_r]], columns=["Usuario", "Password", "Rol"])
                            df_final = pd.concat([df_users, df_nuevo], ignore_index=True)
                            guardar_df_hoja("Usuarios", df_final)
                            st.success(f"Usuario '{new_u}' creado exitosamente en Google Sheets.")
                    else:
                        st.warning("Complete todos los campos.")

            # Tab 4: Gestionar y Eliminar Usuarios
            with tab4:
                st.subheader("🗑️ Lista y Eliminación de Usuarios")
                df_users = cargar_df_hoja("Usuarios", ["Usuario", "Password", "Rol"])
                st.dataframe(df_users, use_container_width=True)
                
                u_eliminar = st.selectbox("Seleccione usuario a eliminar", df_users["Usuario"].tolist() if not df_users.empty else [])
                if st.button("❌ Eliminar Usuario Seleccionado"):
                    if u_eliminar:
                        if u_eliminar.lower() == st.session_state.username.lower():
                            st.error("No puedes eliminar tu propio usuario en sesión.")
                        else:
                            df_final = df_users[df_users["Usuario"].astype(str).str.lower() != str(u_eliminar).lower()]
                            guardar_df_hoja("Usuarios", df_final)
                            st.success(f"Usuario '{u_eliminar}' eliminado correctamente.")
                            st.rerun()

            # Tab 5: Restablecer Clave Directo
            with tab5:
                st.subheader("🔑 Restablecer Contraseña Manual")
                usuario_reset = st.text_input("Usuario a restablecer")
                nueva_pass = st.text_input("Nueva contraseña", type="password")
                if st.button("Restablecer Contraseña"):
                    df_users = cargar_df_hoja("Usuarios", ["Usuario", "Password", "Rol"])
                    if usuario_reset.lower() in df_users["Usuario"].astype(str).str.lower().values:
                        df_users.loc[df_users["Usuario"].astype(str).str.lower() == usuario_reset.lower(), "Password"] = nueva_pass
                        guardar_df_hoja("Usuarios", df_users)
                        st.success(f"Contraseña actualizada para {usuario_reset} en Google Sheets.")
                    else:
                        st.error("Usuario no encontrado")
        else:
            st.warning("No tienes permiso para ver esta sección.")