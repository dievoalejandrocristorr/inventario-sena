import datetime
import json
import os
from google.oauth2.service_account import Credentials
import gspread
import pandas as pd
import streamlit as st

# --- CONFIGURACIÓN DE ARCHIVOS Y GOOGLE SHEETS ---
ARCHIVO_MEMORIAS = "Memorias.xlsx"
ARCHIVO_USUARIOS = "usuarios_taller.csv"
ARCHIVO_LOG = "auditoria_taller.txt"
ARCHIVO_SOLICITUDES = "solicitudes_password.txt"

# Configuración de la página
st.set_page_config(page_title="Control Taller CIMM", layout="wide")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def conectar_gsheets():
  if "gcp_service_account" in st.secrets:
    service_account_info = dict(st.secrets["gcp_service_account"])
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


# Inicializar archivo de usuarios si no existe
if not os.path.exists(ARCHIVO_USUARIOS):
  df_u = pd.DataFrame(
      [["alejandro", "Alejandro312.", "ADMIN"]],
      columns=["Usuario", "Password", "Rol"],
  )
  df_u.to_csv(ARCHIVO_USUARIOS, index=False)

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

  # --- PANTALLA DE SOLICITUD DE RECUPERACIÓN (Para los aprendices) ---
  st.markdown("---")
  with st.expander("🚨 ¿Olvidaste tu contraseña? Solicita acceso aquí"):
    st.write(
        "Ingresa tus datos. El administrador revisará y aprobará tu cambio en el"
        " panel."
    )

    user_solicita = st.text_input("Tu usuario:", key="user_sol")
    nueva_pass_solicita = st.text_input(
        "Nueva contraseña que deseas:", type="password", key="pass_sol"
    )

    if st.button("Enviar solicitud al Administrador"):
      if user_solicita and nueva_pass_solicita:
        df_u = pd.read_csv(ARCHIVO_USUARIOS)

        # Verificar si el usuario realmente existe
        if user_solicita.lower() in df_u["Usuario"].values:
          fecha_sol = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

          # Guardamos la solicitud en el archivo de texto en espera
          linea_solicitud = (
              f"{fecha_sol},{user_solicita.lower()},{nueva_pass_solicita}\n"
          )
          with open(ARCHIVO_SOLICITUDES, "a") as f:
            f.write(linea_solicitud)

          st.success(
              "¡Solicitud enviada! Dile a Alejandro que te la apruebe en el"
              " panel."
          )
        else:
          st.error("El usuario ingresado no existe en el sistema.")
      else:
        st.warning("Por favor rellena ambos campos.")

  if boton_entrar:
    df_u = pd.read_csv(ARCHIVO_USUARIOS)

    user_match = df_u[
        (df_u["Usuario"] == user.lower()) & (df_u["Password"] == pas)
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
      [
          "Inventario",
          "Registrar Movimiento",
          "Guía para Aprendices",
          "Panel Admin",
      ],
  )

  if st.sidebar.button("Cerrar Sesión"):
    st.session_state.autenticado = False
    st.rerun()

  # =========================================================
  # 1. INVENTARIO (Conectado a Google Sheets)
  # =========================================================
  if opcion == "Inventario":

    st.header("📊 Saldo de Materiales en Taller")

    try:
      cliente = conectar_gsheets()
      if cliente:
        sheet = cliente.open("general").sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        busqueda = st.text_input("Buscar material (ej: Marco, 3893, Sillar)")

        if busqueda and not df.empty:
          df = df[
              df["Descripcion"].astype(str).str.contains(
                  busqueda, case=False, na=False
              )
              | df["Referencia"].astype(str).str.contains(
                  busqueda, case=False, na=False
              )
          ]

        if not df.empty:
          st.dataframe(df, use_container_width=True)
        else:
          st.info("No hay registros en la hoja de cálculo.")
      else:
        st.error(
            "No se pudieron cargar las credenciales de Google Sheets. Revisa"
            " tus secretos."
        )
    except Exception as e:
      st.error(f"Error al conectar con la hoja de Google Sheets: {e}")

  # =========================================================
  # 2. REGISTRAR MOVIMIENTO
  # =========================================================
  elif opcion == "Registrar Movimiento":

    st.header("📝 Registro de Entradas y Salidas")

    with st.form("registro"):
      tipo = st.selectbox(
          "Tipo de movimiento", ["SALIDA (Gasto)", "ENTRADA (Ingreso)"]
      )
      ref = st.text_input("Referencia del material")
      cant = st.text_input("Cantidad (cm o Unidades)")
      obra = st.text_input("Nota / Obra / Destino")

      enviar = st.form_submit_button("Guardar Registro")

      if enviar:
        fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        log = f"[{fecha}] | {tipo} | {st.session_state.username} | REF: {ref} | CANT: {cant} | NOTA: {obra}\n"

        with open(ARCHIVO_LOG, "a") as f:
          f.write(log)

        st.success("¡Registro guardado con éxito!")

  # =========================================================
  # 3. GUÍA PARA APRENDICES
  # =========================================================
  elif opcion == "Guía para Aprendices":

    st.header("📏 Consulta de Perfiles por Proyecto")
    proyecto = st.selectbox("Seleccione el proyecto", ["PTA", "DBB", "PB", "DO"])

    try:
      df_m = pd.read_excel(ARCHIVO_MEMORIAS, sheet_name=proyecto)
      st.subheader(f"Perfiles necesarios para {proyecto}")
      st.table(df_m.iloc[29:35, [10, 12, 14]])
      st.info("Nota: Verifique los descuentos de corte antes de usar la tronzadora.")
    except:
      st.error("No se pudo cargar la guía de Memorias.xlsx")

  # =========================================================
  # 4. PANEL ADMIN (Con aprobación de contraseñas)
  # =========================================================
  elif opcion == "Panel Admin":

    if st.session_state.rol == "ADMIN":

      st.header("⚙️ Control de Administrador")

      tab1, tab2, tab3, tab4 = st.tabs([
          "Auditoría",
          "📩 Solicitudes de Clave",
          "Crear Usuarios",
          "Restablecer Contraseña Directo",
      ])

      # -----------------------------------
      # TAB 1 - AUDITORÍA
      # -----------------------------------
      with tab1:
        if os.path.exists(ARCHIVO_LOG):
          with open(ARCHIVO_LOG, "r") as f:
            st.text_area("Historial de movimientos", f.read(), height=300)
        else:
          st.write("No hay registros aún.")

      # -----------------------------------
      # TAB 4 - RESTABLECER CONTRASEÑA DIRECTO
      # -----------------------------------
      with tab4:
        st.subheader("🔑 Restablecer Contraseña Manual")
        usuario_reset = st.text_input("Usuario a restablecer")
        nueva_pass = st.text_input("Nueva contraseña", type="password")

        if st.button("Restablecer Contraseña"):
          df_users = pd.read_csv(ARCHIVO_USUARIOS)
          if usuario_reset.lower() in df_users["Usuario"].values:
            df_users.loc[
                df_users["Usuario"] == usuario_reset.lower(), "Password"
            ] = nueva_pass
            df_users.to_csv(ARCHIVO_USUARIOS, index=False)
            st.success(f"Contraseña actualizada para {usuario_reset}")
          else:
            st.error("Usuario no encontrado")

      # -----------------------------------
      # TAB 2 - GESTIÓN DE SOLICITUDES
      # -----------------------------------
      with tab2:
        st.subheader("📩 Peticiones de cambio pendientes")

        if (
            os.path.exists(ARCHIVO_SOLICITUDES)
            and os.path.getsize(ARCHIVO_SOLICITUDES) > 0
        ):
          with open(ARCHIVO_SOLICITUDES, "r") as f:
            lineas = f.readlines()

          solicitudes_pendientes = []
          for i, linea in enumerate(lineas):
            if linea.strip():
              f_sol, u_sol, p_sol = linea.strip().split(",")
              solicitudes_pendientes.append({
                  "id": i,
                  "Fecha": f_sol,
                  "Usuario": u_sol,
                  "Nueva_Clave": p_sol,
              })

          for sol in solicitudes_pendientes:
            col_info, col_btn_si, col_btn_no = st.columns([3, 1, 1])

            with col_info:
              st.write(
                  f"📅 **{sol['Fecha']}** | El usuario **{sol['Usuario']}**"
                  f" solicita cambiar su contraseña a: `{sol['Nueva_Clave']}`"
              )

            with col_btn_si:
              if st.button("✅ Aprobar", key=f"apr_{sol['id']}"):
                df_users = pd.read_csv(ARCHIVO_USUARIOS)
                df_users.loc[
                    df_users["Usuario"] == sol["Usuario"], "Password"
                ] = sol["Nueva_Clave"]
                df_users.to_csv(ARCHIVO_USUARIOS, index=False)

                del lineas[sol["id"]]
                with open(ARCHIVO_SOLICITUDES, "w") as f:
                  f.writelines(lineas)

                st.success(f"¡Cambio aplicado a {sol['Usuario']}!")
                st.rerun()

            with col_btn_no:
              if st.button("❌ Rechazar", key=f"rec_{sol['id']}"):
                del lineas[sol["id"]]
                with open(ARCHIVO_SOLICITUDES, "w") as f:
                  f.writelines(lineas)

                st.warning("Solicitud descartada.")
                st.rerun()
            st.markdown("---")
        else:
          st.info(
              "No tienes solicitudes de cambio de contraseña pendientes por"
              " ahora. 👍"
          )

      # -----------------------------------
      # TAB 3 - CREAR USUARIOS
      # -----------------------------------
      with tab3:
        new_u = st.text_input("Nombre del compañero")
        new_p = st.text_input("Contraseña para él", type="password")
        new_r = st.selectbox("Rol", ["USER", "ADMIN"])

        if st.button("Crear Usuario"):
          if new_u and new_p:
            df_users_actual = pd.read_csv(ARCHIVO_USUARIOS)
            df_nuevo = pd.DataFrame(
                [[new_u.lower(), new_p, new_r]],
                columns=["Usuario", "Password", "Rol"],
            )
            df_final = pd.concat(
                [df_users_actual, df_nuevo], ignore_index=True
            )
            df_final.to_csv(ARCHIVO_USUARIOS, index=False)
            st.success(f"Usuario {new_u} creado.")
          else:
            st.warning("Complete todos los campos.")
    else:
      st.warning("No tienes permiso para ver esta sección.")