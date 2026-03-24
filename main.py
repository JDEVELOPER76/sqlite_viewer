import flet as ft
from base_modelo import BaseModelo


def main(page:ft.Page):
    # Permitir callback para volver
    page.title = "Mananger de Base de Datos"
    page.window.maximized = True
    page.scroll = ft.ScrollMode.AUTO

    modelo = BaseModelo()
    estado = {
        "tabla_actual": None,
        "filas": [],
        "filas_completas": [],
        "columnas": [],
        "indice_seleccionado": None,
        "ruta_db": "",
    }

    def mostrar_mensaje(texto: str, error: bool = False):
        barra = ft.SnackBar(
            content=ft.Text(texto),
            bgcolor=ft.Colors.RED_300 if error else ft.Colors.GREEN_300,
        )
        page.show_dialog(barra)

    buscador = ft.TextField(
        label="Buscar en tabla",
        hint_text="Escribe texto para filtrar filas",
        prefix_icon=ft.icons.Icons.SEARCH,
        expand=True,
    )

    ruta_db_texto = ft.Text("Sin base de datos seleccionada", size=12)

    selector_tabla = ft.Dropdown(
        label="Tablas",
        options=[],
        width=280,
    )

    info_tabla = ft.Text("Conecta una base de datos para comenzar", size=12)

    cargar_tabla = ft.DataTable(
        columns=[ft.DataColumn(ft.Text("Sin columnas"))],
        rows=[],
        column_spacing=20,
        horizontal_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
        vertical_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
    )

    tabla_scroll_x = ft.Row(
        controls=[ft.Container(content=cargar_tabla, padding=8)],
        scroll=ft.ScrollMode.AUTO,
    )

    contenedor_tabla = ft.Container(
        content=ft.Column(
            controls=[info_tabla, tabla_scroll_x],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        border=ft.Border.all(1, ft.Colors.GREY_300),
        border_radius=8,
        padding=8,
        expand=True,
    )

    def filtrar_filas(texto: str):
        texto = (texto or "").strip().lower()
        if not texto:
            return estado["filas_completas"]

        filas_filtradas = []
        for fila in estado["filas_completas"]:
            for col in estado["columnas"]:
                valor = fila.get(col, "")
                if texto in str(valor).lower():
                    filas_filtradas.append(fila)
                    break
        return filas_filtradas

    def renderizar_tabla(filas: list[dict], columnas: list[str]):
        estado["filas"] = filas
        estado["columnas"] = columnas
        estado["indice_seleccionado"] = None

        if not columnas:
            cargar_tabla.columns = [ft.DataColumn(ft.Text("Sin columnas"))]
            cargar_tabla.rows = []
            info_tabla.value = "No hay columnas disponibles"
            page.update()
            return

        cargar_tabla.columns = [ft.DataColumn(ft.Text(col)) for col in columnas]
        cargar_tabla.rows = []

        for i, fila in enumerate(filas):
            celdas = [ft.DataCell(ft.Text(str(fila.get(col, "")))) for col in columnas]
            cargar_tabla.rows.append(
                ft.DataRow(
                    cells=celdas,
                    on_select_change=lambda e, idx=i: seleccionar_fila(idx),
                )
            )

        if filas:
            info_tabla.value = f"Registros cargados: {len(filas)}"
        else:
            info_tabla.value = "La tabla no tiene registros"

        page.update()

    def aplicar_filtro_actual():
        filas_filtradas = filtrar_filas(buscador.value)
        renderizar_tabla(filas_filtradas, estado["columnas"])

    def on_buscar_change(e):
        aplicar_filtro_actual()

    def seleccionar_fila(indice: int):
        estado["indice_seleccionado"] = indice
        for i, fila in enumerate(cargar_tabla.rows):
            fila.selected = i == indice
        page.update()

    def cargar_filas(tabla: str):
        if not tabla:
            return

        estado["tabla_actual"] = tabla
        filas = modelo.leer_tabla(tabla)
        columnas_meta = modelo.obtener_columnas(tabla)
        columnas = [c["name"] for c in columnas_meta]
        estado["filas_completas"] = filas
        estado["columnas"] = columnas
        aplicar_filtro_actual()

    def conectar_con_ruta(ruta: str):
        try:
            modelo.conectar(ruta)
            estado["ruta_db"] = ruta
            ruta_db_texto.value = f"DB: {ruta}"
            tablas = modelo.obtener_tablas()
            selector_tabla.options = [ft.dropdown.Option(t) for t in tablas]

            if tablas:
                selector_tabla.value = tablas[0]
                cargar_filas(tablas[0])
                mostrar_mensaje(f"Conectado. Tablas encontradas: {len(tablas)}")
            else:
                estado["tabla_actual"] = None
                estado["filas_completas"] = []
                estado["columnas"] = []
                renderizar_tabla([], [])
                info_tabla.value = "No se encontraron tablas de usuario"
                page.update()
                mostrar_mensaje("Conectado, pero no hay tablas", error=True)

        except Exception as ex:
            mostrar_mensaje(f"Error al conectar: {ex}", error=True)

    file_picker = ft.FilePicker()
    page.services.append(file_picker)

    async def seleccionar_db(e):
        archivos = await file_picker.pick_files(
            dialog_title="Selecciona una base SQLite",
            allow_multiple=False,
            allowed_extensions=["db", "sqlite", "sqlite3"],
            file_type=ft.FilePickerFileType.CUSTOM,
        )

        if not archivos:
            return

        ruta = archivos[0].path
        if not ruta:
            mostrar_mensaje("No se pudo obtener la ruta del archivo seleccionado", error=True)
            return

        conectar_con_ruta(ruta)

    buscador.on_change = on_buscar_change

    def on_tabla_change(e):
        if selector_tabla.value:
            try:
                cargar_filas(selector_tabla.value)
            except Exception as ex:
                mostrar_mensaje(f"No se pudo cargar la tabla: {ex}", error=True)

    def editar_seleccion(e):
        idx = estado["indice_seleccionado"]
        tabla = estado["tabla_actual"]
        if idx is None or tabla is None:
            mostrar_mensaje("Selecciona una fila primero", error=True)
            return

        fila_original = estado["filas"][idx]
        fields = {}

        controles = []
        for col in estado["columnas"]:
            valor = "" if fila_original.get(col) is None else str(fila_original.get(col))
            tf = ft.TextField(label=col, value=valor)
            fields[col] = tf
            controles.append(tf)

        def guardar_edicion(ev):
            try:
                fila_nueva = {c: fields[c].value for c in estado["columnas"]}
                modelo.actualizar_fila(tabla, fila_original, fila_nueva)
                page.pop_dialog()
                cargar_filas(tabla)
                mostrar_mensaje("Fila actualizada")
            except Exception as ex:
                mostrar_mensaje(f"Error al editar: {ex}", error=True)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Editar fila"),
            content=ft.Container(
                content=ft.Column(controls=controles, scroll=ft.ScrollMode.AUTO),
                width=600,
                height=400,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Guardar", on_click=guardar_edicion),
            ],
        )

        page.show_dialog(dialogo)
    def añadir_datos(e):
        tabla = estado["tabla_actual"]
        if tabla is None:
            mostrar_mensaje("Selecciona una tabla primero", error=True)
            return

        fields = {}
        controles = []
        for col in estado["columnas"]:
            tf = ft.TextField(label=col, value="")
            fields[col] = tf
            controles.append(tf)

        def guardar_nuevo(ev):
            try:
                fila_nueva = {c: fields[c].value for c in estado["columnas"]}
                modelo.insertar_fila(tabla, fila_nueva)
                page.pop_dialog()
                cargar_filas(tabla)
                mostrar_mensaje("Fila agregada")
            except Exception as ex:
                mostrar_mensaje(f"Error al agregar: {ex}", error=True)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Añadir nueva fila"),
            content=ft.Container(
                content=ft.Column(controls=controles, scroll=ft.ScrollMode.AUTO),
                width=600,
                height=400,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Guardar", on_click=guardar_nuevo),
            ],
        )

        page.show_dialog(dialogo)
    def eliminar_seleccion(e):
        idx = estado["indice_seleccionado"]
        tabla = estado["tabla_actual"]
        if idx is None or tabla is None:
            mostrar_mensaje("Selecciona una fila primero", error=True)
            return

        fila_original = estado["filas"][idx]

        def confirmar_eliminar(ev):
            try:
                modelo.eliminar_fila(tabla, fila_original)
                page.pop_dialog()
                cargar_filas(tabla)
                mostrar_mensaje("Fila eliminada")
            except Exception as ex:
                mostrar_mensaje(f"Error al eliminar: {ex}", error=True)

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar eliminacion"),
            content=ft.Text("Esta accion no se puede deshacer.\n\nDeseas eliminar la fila seleccionada?"),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.Button("Eliminar", color=ft.Colors.WHITE, bgcolor=ft.Colors.RED, on_click=confirmar_eliminar),
            ],
        )
        page.show_dialog(dialogo)
    #on_change
    selector_tabla.on_text_change = on_tabla_change

    barra_superior = ft.Row(
        controls=[
            ft.Button("Seleccionar DB", icon=ft.icons.Icons.FOLDER_OPEN, on_click=seleccionar_db),
            ft.Container(content=buscador, expand=True),
        ]
    )

    acciones = ft.Row(
        controls=[
            selector_tabla,
            ft.Button("Editar seleccion", icon=ft.icons.Icons.EDIT, on_click=editar_seleccion),
            ft.Button("Añadir Datos", icon=ft.icons.Icons.ADD, on_click = añadir_datos),
            ft.Button("Eliminar seleccion", icon=ft.icons.Icons.DELETE, on_click=eliminar_seleccion),
        ],
        wrap=True,
    )

    page.add(
        ft.Column(
            controls=[
                ft.Text("Gestor dinamico de SQLite", size=22, weight=ft.FontWeight.BOLD),
                barra_superior,
                ruta_db_texto,
                acciones,
                contenedor_tabla,
            ],
            spacing=10,
            expand=True,
        )
    )

ft.run(main)